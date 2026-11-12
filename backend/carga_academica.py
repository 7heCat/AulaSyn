"""
HU7 · Carga académica de los docentes   |   HU8 · Validación de disponibilidad

  GET    /carga-academica                    página (permiso gestionar_docentes)
  GET    /api/carga-academica/datos          listas para los formularios
  GET    /api/carga-academica                resumen por docente  (?docente=&periodo=)
  GET    /api/carga-academica/<id_docente>   materias, grupos y horario de un docente
  GET    /api/grupos                         grupos del periodo     (?periodo=)
  POST   /api/grupos                         crear grupo            (gestionar_grupos)
  POST   /api/asignaciones/validar           HU8: valida sin guardar
  POST   /api/asignaciones                   HU8: valida y guarda la clase
  DELETE /api/asignaciones/<id>              quitar una clase

Reglas de la HU8 al asignar una clase (bloquean con 409):
  1. El docente debe estar activo y aprobado.
  2. Debe tener disponibilidad registrada para ese día, sede y franja
     (la franja de la disponibilidad debe cubrir la de la clase).
     Si la disponibilidad es de una asignatura concreta, debe ser la del grupo.
  3. No puede tener otra clase que se cruce en el tiempo ese día, en el mismo
     periodo (las franjas se traslapan: 13-16 y 14-17 chocan, aunque sean distintas).
  4. El grupo tampoco puede tener dos clases que se crucen.
Avisa sin bloquear: el docente no tiene asociada la asignatura (HU6).
"""
import re
import unicodedata

import psycopg
from flask import Blueprint, current_app, jsonify, render_template, request
from psycopg.rows import dict_row

from config.database import obtener_conexion
from permisos import requiere_permiso

carga_bp = Blueprint("carga_academica", __name__)

# Como se guardan los días en la base de datos (sin tildes).
DIAS = ("Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado")
# Misma normalización en SQL, por si disponibilidad_docente tuviera tildes.
SQL_DIA = "translate({c}, 'éÉáÁ', 'eEaA')"


def _err(mensaje, codigo, **extra):
    return jsonify({"mensaje": mensaje, **extra}), codigo


def normalizar_dia(valor):
    """'Miércoles' / 'miercoles' -> 'Miercoles'. None si no es un día válido."""
    if not isinstance(valor, str):
        return None
    sin_tilde = "".join(
        c for c in unicodedata.normalize("NFD", valor.strip())
        if unicodedata.category(c) != "Mn"
    ).capitalize()
    return sin_tilde if sin_tilde in DIAS else None


def _entero(valor):
    """int estricto (rechaza bool, texto, decimales)."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _hora(t):
    return t.strftime("%H:%M")


# ---------------------------------------------------------------------
# Validación (HU8) — se usa con la conexión/transacción ya abierta
# ---------------------------------------------------------------------
def validar_asignacion(cur, id_grupo, id_usuario, id_sede, id_franja, dia, bloquear=False):
    """
    Devuelve (error, advertencias, contexto). error es (mensaje, motivo) o None.
    Con bloquear=True toma un candado sobre el docente (FOR UPDATE) para que dos
    asignaciones simultáneas no puedan crear un choque de horario.
    """
    cur.execute(
        "SELECT id_usuario, nombres, apellidos, rol, activo, estado_cuenta FROM public.usuarios "
        "WHERE id_usuario = %s" + (" FOR UPDATE" if bloquear else ""),
        (id_usuario,),
    )
    docente = cur.fetchone()
    if docente is None or docente["rol"] != "profesor":
        return ("El docente seleccionado no existe.", "docente_invalido"), [], None
    if docente["activo"] is not True or docente["estado_cuenta"] != "activo":
        return ("El docente no está activo o aún no ha sido aprobado.", "docente_inactivo"), [], None

    cur.execute(
        "SELECT g.id_grupo, g.periodo, g.codigo, g.id_asignatura, a.nombre AS asignatura "
        "FROM public.grupos g JOIN public.asignaturas a USING (id_asignatura) "
        "WHERE g.id_grupo = %s AND g.activo IS TRUE", (id_grupo,))
    grupo = cur.fetchone()
    if grupo is None:
        return ("El grupo seleccionado no existe.", "grupo_invalido"), [], None

    cur.execute("SELECT nombre FROM public.sedes WHERE id_sede = %s AND activa IS TRUE", (id_sede,))
    sede = cur.fetchone()
    if sede is None:
        return ("La sede seleccionada no existe.", "sede_invalida"), [], None

    cur.execute("SELECT nombre, hora_inicio, hora_fin FROM public.franjas_horarias "
                "WHERE id_franja = %s AND activa IS TRUE", (id_franja,))
    franja = cur.fetchone()
    if franja is None:
        return ("La franja horaria seleccionada no existe.", "franja_invalida"), [], None

    nombre_docente = f"{docente['nombres']} {docente['apellidos']}"
    horario = f"{dia} {_hora(franja['hora_inicio'])}–{_hora(franja['hora_fin'])}"
    contexto = {"docente": nombre_docente, "grupo": grupo, "sede": sede["nombre"],
                "franja": franja["nombre"], "horario": horario}

    # 2. Disponibilidad registrada (HU5)
    cur.execute(
        f"""
        SELECT 1
        FROM public.disponibilidad_docente d
        JOIN public.franjas_horarias fd ON fd.id_franja = d.id_franja
        WHERE d.id_usuario = %s AND d.id_sede = %s AND d.disponible IS TRUE
          AND {SQL_DIA.format(c='d.dia_semana')} = %s
          AND fd.hora_inicio <= %s AND fd.hora_fin >= %s
          AND (d.id_asignatura IS NULL OR d.id_asignatura = %s)
        LIMIT 1
        """,
        (id_usuario, id_sede, dia, franja["hora_inicio"], franja["hora_fin"], grupo["id_asignatura"]),
    )
    if cur.fetchone() is None:
        return (
            f"{nombre_docente} no tiene disponibilidad registrada el {horario} en {sede['nombre']}"
            f" para {grupo['asignatura']}.",
            "sin_disponibilidad",
        ), [], contexto

    # 3. Choque con otra clase del docente
    cur.execute(
        f"""
        SELECT a.nombre AS asignatura, g.codigo, s.nombre AS sede, f.hora_inicio, f.hora_fin
        FROM public.asignacion_clase ac
        JOIN public.grupos g ON g.id_grupo = ac.id_grupo
        JOIN public.asignaturas a ON a.id_asignatura = g.id_asignatura
        JOIN public.sedes s ON s.id_sede = ac.id_sede
        JOIN public.franjas_horarias f ON f.id_franja = ac.id_franja
        WHERE ac.id_usuario = %s AND ac.dia_semana = %s AND g.periodo = %s
          AND f.hora_inicio < %s AND %s < f.hora_fin
        LIMIT 1
        """,
        (id_usuario, dia, grupo["periodo"], franja["hora_fin"], franja["hora_inicio"]),
    )
    choque = cur.fetchone()
    if choque:
        return (
            f"{nombre_docente} ya dicta {choque['asignatura']} (grupo {choque['codigo']}) en "
            f"{choque['sede']} el {dia} {_hora(choque['hora_inicio'])}–{_hora(choque['hora_fin'])}, "
            "que se cruza con este horario.",
            "choque_docente",
        ), [], contexto

    # 4. Choque dentro del mismo grupo
    cur.execute(
        """
        SELECT f.hora_inicio, f.hora_fin
        FROM public.asignacion_clase ac
        JOIN public.franjas_horarias f ON f.id_franja = ac.id_franja
        WHERE ac.id_grupo = %s AND ac.dia_semana = %s
          AND f.hora_inicio < %s AND %s < f.hora_fin
        LIMIT 1
        """,
        (id_grupo, dia, franja["hora_fin"], franja["hora_inicio"]),
    )
    if cur.fetchone():
        return (
            f"El grupo {grupo['codigo']} ya tiene una clase que se cruza con el {horario}.",
            "choque_grupo",
        ), [], contexto

    advertencias = []
    cur.execute("SELECT 1 FROM public.docente_asignatura WHERE id_usuario = %s AND id_asignatura = %s",
                (id_usuario, grupo["id_asignatura"]))
    if cur.fetchone() is None:
        advertencias.append(f"{nombre_docente} no tiene asociada la asignatura {grupo['asignatura']}.")
    return None, advertencias, contexto


def _leer_asignacion(datos):
    ids = {k: _entero(datos.get(k)) for k in ("id_grupo", "id_usuario", "id_sede", "id_franja")}
    dia = normalizar_dia(datos.get("dia_semana"))
    if any(v is None for v in ids.values()) or dia is None:
        return None, None
    return ids, dia


MSG_DATOS = "Selecciona el docente, el grupo, el día, la sede y la franja horaria."
MSG_500 = "No fue posible completar la operación. Inténtalo más tarde."


@carga_bp.route("/api/asignaciones/validar", methods=["POST"])
@requiere_permiso("gestionar_grupos")
def validar():
    datos = request.get_json(silent=True)
    ids, dia = _leer_asignacion(datos if isinstance(datos, dict) else {})
    if ids is None:
        return _err(MSG_DATOS, 400)
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            error, avisos, _ = validar_asignacion(cur, ids["id_grupo"], ids["id_usuario"],
                                                  ids["id_sede"], ids["id_franja"], dia)
    except psycopg.Error:
        current_app.logger.exception("Error al validar asignación")
        return _err(MSG_500, 500)
    if error:
        return jsonify({"valido": False, "mensaje": error[0], "motivo": error[1]})
    return jsonify({"valido": True, "mensaje": "La asignación es válida.", "advertencias": avisos})


@carga_bp.route("/api/asignaciones", methods=["POST"])
@requiere_permiso("gestionar_grupos")
def asignar():
    datos = request.get_json(silent=True)
    ids, dia = _leer_asignacion(datos if isinstance(datos, dict) else {})
    if ids is None:
        return _err(MSG_DATOS, 400)
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            error, avisos, _ = validar_asignacion(cur, ids["id_grupo"], ids["id_usuario"],
                                                  ids["id_sede"], ids["id_franja"], dia, bloquear=True)
            if error:
                codigo = 404 if error[1] in ("docente_invalido", "grupo_invalido", "sede_invalida",
                                              "franja_invalida") else 409
                return _err(error[0], codigo, motivo=error[1])
            cur.execute(
                "INSERT INTO public.asignacion_clase (id_grupo, id_usuario, id_sede, id_franja, dia_semana) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id_asignacion",
                (ids["id_grupo"], ids["id_usuario"], ids["id_sede"], ids["id_franja"], dia),
            )
            nuevo = cur.fetchone()["id_asignacion"]
    except psycopg.errors.UniqueViolation:
        return _err("Esa clase ya está asignada.", 409, motivo="duplicada")
    except psycopg.Error:
        current_app.logger.exception("Error al asignar clase")
        return _err(MSG_500, 500)
    return jsonify({"mensaje": "Clase asignada correctamente.", "id_asignacion": nuevo,
                    "advertencias": avisos}), 201


@carga_bp.route("/api/asignaciones/<int:id_asignacion>", methods=["DELETE"])
@requiere_permiso("gestionar_grupos")
def quitar(id_asignacion):
    try:
        with obtener_conexion() as con, con.cursor() as cur:
            cur.execute("DELETE FROM public.asignacion_clase WHERE id_asignacion = %s", (id_asignacion,))
            borradas = cur.rowcount
    except psycopg.Error:
        current_app.logger.exception("Error al quitar clase")
        return _err(MSG_500, 500)
    if not borradas:
        return _err("La clase no existe.", 404)
    return jsonify({"mensaje": "Clase retirada correctamente."})


# ---------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------
@carga_bp.route("/api/grupos", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def listar_grupos():
    periodo = request.args.get("periodo", "").strip()
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT g.id_grupo, g.periodo, g.codigo, g.codigo_asignatura, a.id_asignatura,
                       a.nombre AS asignatura, a.semestre,
                       (SELECT count(*)::int FROM public.asignacion_clase ac
                         WHERE ac.id_grupo = g.id_grupo) AS clases
                FROM public.grupos g JOIN public.asignaturas a USING (id_asignatura)
                WHERE g.activo IS TRUE AND (%s = '' OR g.periodo = %s)
                ORDER BY g.periodo DESC, a.semestre, a.nombre, g.codigo
                """,
                (periodo, periodo),
            )
            return jsonify({"grupos": cur.fetchall()})
    except psycopg.Error:
        current_app.logger.exception("Error al listar grupos")
        return _err(MSG_500, 500)


@carga_bp.route("/api/grupos", methods=["POST"])
@requiere_permiso("gestionar_grupos")
def crear_grupo():
    d = request.get_json(silent=True)
    d = d if isinstance(d, dict) else {}
    periodo = d.get("periodo").strip() if isinstance(d.get("periodo"), str) else ""
    codigo = d.get("codigo").strip().upper() if isinstance(d.get("codigo"), str) else ""
    cod_asig = d.get("codigo_asignatura").strip().upper() if isinstance(d.get("codigo_asignatura"), str) else ""
    id_asig = _entero(d.get("id_asignatura"))
    if not re.fullmatch(r"\d{5}", periodo):
        return _err("El periodo debe tener 5 dígitos, por ejemplo 22026.", 400)
    if not re.fullmatch(r"[A-Z0-9]{1,20}", codigo):
        return _err("El código del grupo solo puede tener letras y números (ej. 941A).", 400)
    if cod_asig and not re.fullmatch(r"[A-Z0-9]{1,20}", cod_asig):
        return _err("El código de la asignatura solo puede tener letras y números (ej. FI303273).", 400)
    if id_asig is None:
        return _err("Selecciona la asignatura del grupo.", 400)
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT 1 FROM public.asignaturas WHERE id_asignatura = %s AND activa IS TRUE", (id_asig,))
            if cur.fetchone() is None:
                return _err("La asignatura seleccionada no existe.", 404)
            cur.execute(
                "INSERT INTO public.grupos (periodo, codigo, id_asignatura, codigo_asignatura) "
                "VALUES (%s, %s, %s, %s) RETURNING id_grupo",
                (periodo, codigo, id_asig, cod_asig or None),
            )
            nuevo = cur.fetchone()["id_grupo"]
    except psycopg.errors.UniqueViolation:
        return _err("Ya existe ese grupo para la asignatura y el periodo.", 409)
    except psycopg.Error:
        current_app.logger.exception("Error al crear grupo")
        return _err(MSG_500, 500)
    return jsonify({"mensaje": "Grupo creado correctamente.", "id_grupo": nuevo}), 201


# ---------------------------------------------------------------------
# HU7 · Carga académica
# ---------------------------------------------------------------------
@carga_bp.route("/carga-academica")
@requiere_permiso("gestionar_docentes")
def pagina_carga_academica():
    return render_template("carga_academica.html")


@carga_bp.route("/api/carga-academica/datos", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def datos_formularios():
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id_usuario, nombres || ' ' || apellidos AS nombre FROM public.usuarios "
                        "WHERE rol = 'profesor' AND activo IS TRUE AND estado_cuenta = 'activo' ORDER BY 2")
            docentes = cur.fetchall()
            cur.execute("SELECT id_sede, nombre FROM public.sedes WHERE activa IS TRUE ORDER BY nombre")
            sedes = cur.fetchall()
            cur.execute("SELECT id_franja, nombre, jornada, hora_inicio, hora_fin FROM public.franjas_horarias "
                        "WHERE activa IS TRUE ORDER BY hora_inicio, hora_fin")
            franjas = cur.fetchall()
            cur.execute("SELECT id_asignatura, nombre, semestre FROM public.asignaturas "
                        "WHERE activa IS TRUE ORDER BY semestre, nombre")
            asignaturas = cur.fetchall()
            cur.execute("SELECT DISTINCT periodo FROM public.grupos ORDER BY periodo DESC")
            periodos = [f["periodo"] for f in cur.fetchall()]
        for f in franjas:
            f["hora_inicio"], f["hora_fin"] = _hora(f["hora_inicio"]), _hora(f["hora_fin"])
        return jsonify({"docentes": docentes, "sedes": sedes, "franjas": franjas,
                        "asignaturas": asignaturas, "periodos": periodos, "dias": list(DIAS)})
    except psycopg.Error:
        current_app.logger.exception("Error al cargar datos")
        return _err(MSG_500, 500)


@carga_bp.route("/api/carga-academica", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def resumen_carga():
    docente = request.args.get("docente", "").strip()
    periodo = request.args.get("periodo", "").strip()
    texto = docente.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT u.id_usuario, u.nombres || ' ' || u.apellidos AS docente, u.correo,
                       count(DISTINCT x.id_asignatura)::int AS asignaturas,
                       count(DISTINCT x.id_grupo)::int      AS grupos,
                       count(x.id_asignacion)::int          AS clases,
                       COALESCE(round(sum(x.horas)::numeric, 1), 0)::float AS horas_semana
                FROM public.usuarios u
                LEFT JOIN (
                    SELECT ac.id_asignacion, ac.id_usuario, g.id_grupo, g.id_asignatura,
                           extract(epoch FROM (f.hora_fin - f.hora_inicio)) / 3600.0 AS horas
                    FROM public.asignacion_clase ac
                    JOIN public.grupos g ON g.id_grupo = ac.id_grupo
                    JOIN public.franjas_horarias f ON f.id_franja = ac.id_franja
                    WHERE (%s = '' OR g.periodo = %s)
                ) x ON x.id_usuario = u.id_usuario
                WHERE u.rol = 'profesor' AND u.activo IS TRUE AND u.estado_cuenta = 'activo'
                  AND (%s = '' OR (u.nombres || ' ' || u.apellidos) ILIKE %s OR u.correo ILIKE %s)
                GROUP BY u.id_usuario
                ORDER BY u.nombres, u.apellidos
                """,
                (periodo, periodo, docente, f"%{texto}%", f"%{texto}%"),
            )
            return jsonify({"docentes": cur.fetchall()})
    except psycopg.Error:
        current_app.logger.exception("Error en resumen de carga")
        return _err(MSG_500, 500)


@carga_bp.route("/api/carga-academica/<int:id_docente>", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def detalle_carga(id_docente):
    periodo = request.args.get("periodo", "").strip()
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id_usuario, nombres || ' ' || apellidos AS docente, correo FROM public.usuarios "
                        "WHERE id_usuario = %s AND rol = 'profesor'", (id_docente,))
            docente = cur.fetchone()
            if docente is None:
                return _err("El docente no existe.", 404)
            cur.execute(
                """
                SELECT ac.id_asignacion, g.periodo, g.codigo AS grupo, g.codigo_asignatura,
                       a.nombre AS asignatura, a.semestre, ac.dia_semana, s.nombre AS sede,
                       f.nombre AS franja, f.hora_inicio, f.hora_fin
                FROM public.asignacion_clase ac
                JOIN public.grupos g ON g.id_grupo = ac.id_grupo
                JOIN public.asignaturas a ON a.id_asignatura = g.id_asignatura
                JOIN public.sedes s ON s.id_sede = ac.id_sede
                JOIN public.franjas_horarias f ON f.id_franja = ac.id_franja
                WHERE ac.id_usuario = %s AND (%s = '' OR g.periodo = %s)
                ORDER BY g.periodo DESC, a.semestre, a.nombre, g.codigo,
                         array_position(%s::text[], ac.dia_semana::text), f.hora_inicio
                """,
                (id_docente, periodo, periodo, list(DIAS)),
            )
            clases = cur.fetchall()
        for c in clases:
            c["hora_inicio"], c["hora_fin"] = _hora(c["hora_inicio"]), _hora(c["hora_fin"])
        return jsonify({"docente": docente, "clases": clases})
    except psycopg.Error:
        current_app.logger.exception("Error en detalle de carga")
        return _err(MSG_500, 500)
