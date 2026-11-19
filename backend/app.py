
import os
import re

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
    redirect,
    url_for
)

from config.database import obtener_conexion
from werkzeug.security import generate_password_hash, check_password_hash
from permisos import requiere_permiso
from recuperacion import recuperacion_bp
from carga_academica import carga_bp


app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)

app.register_blueprint(recuperacion_bp)
app.register_blueprint(carga_bp)


# ======================================================
# CONFIGURACIÓN DE SEGURIDAD
# ======================================================

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


# ======================================================
# DOMINIOS PERMITIDOS PARA EL REGISTRO
# ======================================================

DOMINIOS_POR_ROL = {
    "estudiante": "@estudiante.uniajc.edu.co",
    "profesor": "@profesores.uniajc.edu.co"
}


# ======================================================
# NAVEGACIÓN DE AULASYN
# ======================================================

@app.route("/")
def inicio():
    if session.get("id_usuario"):
        return redirect(url_for("dashboard"))

    return render_template("autenticacion.html")


@app.route("/inicio")
def dashboard():
    if not session.get("id_usuario"):
        return redirect(url_for("inicio"))

    return render_template("inicio.html")


@app.route("/docentes")
@requiere_permiso("gestionar_docentes")
def gestion_docentes():
    return render_template("docentes.html")



# ======================================================
# HU12 · PROGRAMAS ACADÉMICOS Y PENSUM
# ======================================================

@app.route("/programas-academicos")
@requiere_permiso("gestionar_docentes")
def pagina_programas_academicos():
    return render_template("programas_academicos.html")


@app.route("/api/programas-academicos/programas", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def listar_programas_academicos():
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT p.id_programa, p.nombre, p.descripcion, p.total_semestres,
                       p.activa, p.fecha_creacion,
                       COUNT(a.id_asignatura) AS total_asignaturas
                FROM public.programas_academicos p
                LEFT JOIN public.asignaturas a ON a.id_programa = p.id_programa
                GROUP BY p.id_programa
                ORDER BY p.nombre;
            """)
            filas = cursor.fetchall()
        campos = ("id_programa", "nombre", "descripcion", "total_semestres",
                  "activa", "fecha_creacion", "total_asignaturas")
        return jsonify({"programas": [dict(zip(campos, fila)) for fila in filas]}), 200
    except Exception:
        app.logger.exception("Error al consultar programas académicos")
        return jsonify({"mensaje": "No fue posible consultar los programas académicos."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/programas", methods=["POST"])
@requiere_permiso("gestionar_docentes")
def crear_programa_academico():
    d = request.get_json(silent=True) or {}
    nombre = d.get("nombre", "").strip() if isinstance(d.get("nombre"), str) else ""
    descripcion = d.get("descripcion", "").strip() if isinstance(d.get("descripcion"), str) else ""
    total = d.get("total_semestres", 10)
    if not nombre:
        return jsonify({"mensaje": "El nombre del programa es obligatorio."}), 400
    if not isinstance(total, int) or isinstance(total, bool) or not 1 <= total <= 20:
        return jsonify({"mensaje": "La cantidad de semestres debe estar entre 1 y 20."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.programas_academicos
                    (nombre, descripcion, total_semestres, activa)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id_programa;
            """, (nombre, descripcion or None, total))
            nuevo_id = cursor.fetchone()[0]
        conexion.commit()
        return jsonify({"mensaje": "Programa académico creado correctamente.", "id_programa": nuevo_id}), 201
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al crear programa académico")
        return jsonify({"mensaje": "No fue posible crear el programa. Verifica que no exista otro con el mismo nombre."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/programas/<int:id_programa>", methods=["PUT"])
@requiere_permiso("gestionar_docentes")
def actualizar_programa_academico(id_programa):
    d = request.get_json(silent=True) or {}
    nombre = d.get("nombre", "").strip() if isinstance(d.get("nombre"), str) else ""
    descripcion = d.get("descripcion", "").strip() if isinstance(d.get("descripcion"), str) else ""
    total = d.get("total_semestres")
    if not nombre:
        return jsonify({"mensaje": "El nombre del programa es obligatorio."}), 400
    if not isinstance(total, int) or isinstance(total, bool) or not 1 <= total <= 20:
        return jsonify({"mensaje": "La cantidad de semestres debe estar entre 1 y 20."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(MAX(semestre), 0)
                FROM public.asignaturas WHERE id_programa = %s;
            """, (id_programa,))
            semestre_maximo = cursor.fetchone()[0]
            if total < semestre_maximo:
                return jsonify({"mensaje": f"No puedes reducir el programa a {total} semestres porque ya tiene asignaturas hasta el semestre {semestre_maximo}."}), 400
            cursor.execute("""
                UPDATE public.programas_academicos
                SET nombre=%s, descripcion=%s, total_semestres=%s
                WHERE id_programa=%s;
            """, (nombre, descripcion or None, total, id_programa))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "El programa académico no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Programa académico actualizado correctamente."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al actualizar programa académico")
        return jsonify({"mensaje": "No fue posible actualizar el programa. Verifica que el nombre no esté repetido."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/programas/<int:id_programa>/estado", methods=["PATCH"])
@requiere_permiso("gestionar_docentes")
def cambiar_estado_programa_academico(id_programa):
    d = request.get_json(silent=True) or {}
    activa = d.get("activa")
    if not isinstance(activa, bool):
        return jsonify({"mensaje": "El estado enviado no es válido."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            if not activa:
                cursor.execute("SELECT COUNT(*) FROM public.grupos g JOIN public.asignaturas a ON a.id_asignatura=g.id_asignatura WHERE a.id_programa=%s AND g.activo=TRUE", (id_programa,))
                if cursor.fetchone()[0] > 0:
                    return jsonify({"mensaje": "No puedes desactivar este programa porque tiene grupos activos."}), 400
            cursor.execute("UPDATE public.programas_academicos SET activa=%s WHERE id_programa=%s", (activa, id_programa))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "El programa académico no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Estado del programa actualizado correctamente."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al cambiar estado del programa")
        return jsonify({"mensaje": "No fue posible cambiar el estado del programa."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/asignaturas", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def listar_asignaturas_programa():
    id_programa = request.args.get("id_programa", type=int)
    if not id_programa:
        return jsonify({"mensaje": "Selecciona un programa académico."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id_asignatura, id_programa, nombre, descripcion, activa,
                       semestre, creditos, horas_por_clase, frecuencia
                FROM public.asignaturas
                WHERE id_programa=%s
                ORDER BY semestre NULLS LAST, nombre;
            """, (id_programa,))
            filas = cursor.fetchall()
        campos = ("id_asignatura", "id_programa", "nombre", "descripcion", "activa",
                  "semestre", "creditos", "horas_por_clase", "frecuencia")
        return jsonify({"asignaturas": [dict(zip(campos, fila)) for fila in filas]}), 200
    except Exception:
        app.logger.exception("Error al consultar asignaturas del programa")
        return jsonify({"mensaje": "No fue posible consultar las asignaturas."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/asignaturas", methods=["POST"])
@requiere_permiso("gestionar_docentes")
def crear_asignatura_programa():
    d = request.get_json(silent=True) or {}
    nombre = d.get("nombre", "").strip() if isinstance(d.get("nombre"), str) else ""
    descripcion = d.get("descripcion", "").strip() if isinstance(d.get("descripcion"), str) else ""
    id_programa = d.get("id_programa")
    semestre, creditos, horas = d.get("semestre"), d.get("creditos"), d.get("horas_por_clase")
    frecuencia = d.get("frecuencia", "")
    if not nombre:
        return jsonify({"mensaje": "El nombre de la asignatura es obligatorio."}), 400
    if not isinstance(id_programa, int) or isinstance(id_programa, bool):
        return jsonify({"mensaje": "Selecciona un programa académico."}), 400
    if not isinstance(semestre, int) or isinstance(semestre, bool) or semestre < 1:
        return jsonify({"mensaje": "Selecciona un semestre válido."}), 400
    if not isinstance(creditos, int) or isinstance(creditos, bool) or not 1 <= creditos <= 4:
        return jsonify({"mensaje": "Los créditos deben estar entre 1 y 4."}), 400
    if not isinstance(horas, int) or isinstance(horas, bool) or not 1 <= horas <= 12:
        return jsonify({"mensaje": "La intensidad debe estar entre 1 y 12 horas por clase."}), 400
    if frecuencia not in ("semanal", "quincenal"):
        return jsonify({"mensaje": "Selecciona una frecuencia válida."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT total_semestres FROM public.programas_academicos WHERE id_programa=%s AND activa=TRUE", (id_programa,))
            programa = cursor.fetchone()
            if programa is None:
                return jsonify({"mensaje": "El programa seleccionado no existe o está inactivo."}), 404
            if semestre > programa[0]:
                return jsonify({"mensaje": f"Este programa tiene {programa[0]} semestres. Selecciona uno dentro de ese rango."}), 400
            cursor.execute("""
                INSERT INTO public.asignaturas
                    (id_programa, nombre, descripcion, semestre, creditos, horas_por_clase, frecuencia, activa)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id_asignatura;
            """, (id_programa, nombre, descripcion or None, semestre, creditos, horas, frecuencia))
            nuevo_id = cursor.fetchone()[0]
        conexion.commit()
        return jsonify({"mensaje": "Asignatura creada correctamente.", "id_asignatura": nuevo_id}), 201
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al crear asignatura")
        return jsonify({"mensaje": "No fue posible crear la asignatura. Verifica los datos e intenta nuevamente."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/asignaturas/<int:id_asignatura>", methods=["PUT"])
@requiere_permiso("gestionar_docentes")
def actualizar_asignatura_programa(id_asignatura):
    d = request.get_json(silent=True) or {}
    nombre = d.get("nombre", "").strip() if isinstance(d.get("nombre"), str) else ""
    descripcion = d.get("descripcion", "").strip() if isinstance(d.get("descripcion"), str) else ""
    id_programa = d.get("id_programa")
    semestre, creditos, horas = d.get("semestre"), d.get("creditos"), d.get("horas_por_clase")
    frecuencia = d.get("frecuencia", "")
    if not nombre or not isinstance(id_programa, int) or isinstance(id_programa, bool):
        return jsonify({"mensaje": "Completa el nombre y selecciona un programa."}), 400
    if not isinstance(semestre, int) or isinstance(semestre, bool) or semestre < 1:
        return jsonify({"mensaje": "Selecciona un semestre válido."}), 400
    if not isinstance(creditos, int) or isinstance(creditos, bool) or not 1 <= creditos <= 4:
        return jsonify({"mensaje": "Los créditos deben estar entre 1 y 4."}), 400
    if not isinstance(horas, int) or isinstance(horas, bool) or not 1 <= horas <= 12 or frecuencia not in ("semanal", "quincenal"):
        return jsonify({"mensaje": "Revisa la intensidad y la frecuencia."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT total_semestres FROM public.programas_academicos WHERE id_programa=%s AND activa=TRUE", (id_programa,))
            programa = cursor.fetchone()
            if programa is None:
                return jsonify({"mensaje": "El programa seleccionado no existe o está inactivo."}), 404
            if semestre > programa[0]:
                return jsonify({"mensaje": f"Este programa tiene {programa[0]} semestres."}), 400
            cursor.execute("""
                UPDATE public.asignaturas
                SET id_programa=%s, nombre=%s, descripcion=%s, semestre=%s,
                    creditos=%s, horas_por_clase=%s, frecuencia=%s
                WHERE id_asignatura=%s;
            """, (id_programa, nombre, descripcion or None, semestre, creditos, horas, frecuencia, id_asignatura))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "La asignatura no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Asignatura actualizada correctamente."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al actualizar asignatura")
        return jsonify({"mensaje": "No fue posible actualizar la asignatura."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/programas-academicos/asignaturas/<int:id_asignatura>/estado", methods=["PATCH"])
@requiere_permiso("gestionar_docentes")
def cambiar_estado_asignatura_programa(id_asignatura):
    d = request.get_json(silent=True) or {}
    activa = d.get("activa")
    if not isinstance(activa, bool):
        return jsonify({"mensaje": "El estado enviado no es válido."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            if not activa:
                cursor.execute("SELECT COUNT(*) FROM public.grupos WHERE id_asignatura=%s AND activo=TRUE", (id_asignatura,))
                if cursor.fetchone()[0] > 0:
                    return jsonify({"mensaje": "No puedes desactivar esta asignatura porque tiene grupos activos."}), 400
            cursor.execute("UPDATE public.asignaturas SET activa=%s WHERE id_asignatura=%s", (activa, id_asignatura))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "La asignatura no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Estado actualizado correctamente."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al cambiar estado de asignatura")
        return jsonify({"mensaje": "No fue posible cambiar el estado."}), 500
    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# GESTIÓN INDEPENDIENTE DE GRUPOS
# ======================================================

@app.route("/grupos")
@requiere_permiso("gestionar_grupos")
def pagina_gestion_grupos():
    return render_template("grupos.html")


@app.route("/api/gestion-grupos", methods=["GET"])
@requiere_permiso("gestionar_grupos")
def listar_grupos_gestion():
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT g.id_grupo, g.periodo, g.codigo, g.codigo_asignatura,
                       g.id_asignatura, a.nombre AS asignatura, a.semestre,
                       g.cupo_maximo, g.activo, p.nombre AS programa
                FROM public.grupos g
                JOIN public.asignaturas a ON a.id_asignatura=g.id_asignatura
                JOIN public.programas_academicos p ON p.id_programa=a.id_programa
                ORDER BY g.periodo DESC, p.nombre, a.semestre NULLS LAST, a.nombre, g.codigo;
            """)
            filas = cursor.fetchall()
        campos = ("id_grupo", "periodo", "codigo", "codigo_asignatura", "id_asignatura",
                  "asignatura", "semestre", "cupo_maximo", "activo", "programa")
        return jsonify({"grupos": [dict(zip(campos, fila)) for fila in filas]}), 200
    except Exception:
        app.logger.exception("Error al consultar grupos")
        return jsonify({"mensaje": "No fue posible consultar los grupos."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/gestion-grupos/datos", methods=["GET"])
@requiere_permiso("gestionar_grupos")
def datos_gestion_grupos():
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT a.id_asignatura, a.nombre, a.semestre, p.nombre AS programa
                FROM public.asignaturas a
                JOIN public.programas_academicos p ON p.id_programa=a.id_programa
                WHERE a.activa=TRUE AND p.activa=TRUE
                ORDER BY p.nombre, a.semestre, a.nombre;
            """)
            filas = cursor.fetchall()
        campos = ("id_asignatura", "nombre", "semestre", "programa")
        return jsonify({"asignaturas": [dict(zip(campos, f)) for f in filas]}), 200
    except Exception:
        app.logger.exception("Error al consultar asignaturas para grupos")
        return jsonify({"mensaje": "No fue posible cargar las asignaturas."}), 500
    finally:
        if conexion is not None:
            conexion.close()


def _validar_datos_grupo(d):
    periodo = d.get("periodo", "").strip() if isinstance(d.get("periodo"), str) else ""
    codigo = d.get("codigo", "").strip().upper() if isinstance(d.get("codigo"), str) else ""
    codigo_asignatura = d.get("codigo_asignatura", "").strip().upper() if isinstance(d.get("codigo_asignatura"), str) else ""
    id_asignatura, cupo = d.get("id_asignatura"), d.get("cupo_maximo")
    if not re.fullmatch(r"\d{5}", periodo):
        return None, "El periodo debe tener 5 dígitos, por ejemplo 22026."
    if not re.fullmatch(r"[A-Z0-9]{1,20}", codigo):
        return None, "El código del grupo debe contener entre 1 y 20 letras o números."
    if codigo_asignatura and not re.fullmatch(r"[A-Z0-9]{1,20}", codigo_asignatura):
        return None, "El código de la asignatura solo puede contener letras y números."
    if not isinstance(id_asignatura, int) or isinstance(id_asignatura, bool):
        return None, "Selecciona una asignatura."
    if not isinstance(cupo, int) or isinstance(cupo, bool) or not 1 <= cupo <= 500:
        return None, "El cupo debe estar entre 1 y 500 estudiantes."
    return (periodo, codigo, id_asignatura, codigo_asignatura or None, cupo), None


@app.route("/api/gestion-grupos", methods=["POST"])
@requiere_permiso("gestionar_grupos")
def crear_grupo_gestion():
    valores, error = _validar_datos_grupo(request.get_json(silent=True) or {})
    if error:
        return jsonify({"mensaje": error}), 400
    periodo, codigo, id_asignatura, codigo_asignatura, cupo = valores
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM public.asignaturas a
                JOIN public.programas_academicos p ON p.id_programa=a.id_programa
                WHERE a.id_asignatura=%s AND a.activa=TRUE AND p.activa=TRUE;
            """, (id_asignatura,))
            if cursor.fetchone() is None:
                return jsonify({"mensaje": "La asignatura seleccionada no está disponible."}), 404
            cursor.execute("""
                INSERT INTO public.grupos (periodo, codigo, id_asignatura, codigo_asignatura, cupo_maximo, activo)
                VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id_grupo;
            """, (periodo, codigo, id_asignatura, codigo_asignatura, cupo))
            nuevo_id = cursor.fetchone()[0]
        conexion.commit()
        return jsonify({"mensaje": "Grupo creado correctamente.", "id_grupo": nuevo_id}), 201
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al crear grupo desde Gestión de Grupos")
        return jsonify({"mensaje": "No fue posible crear el grupo. Verifica si ya existe para esa asignatura y periodo."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/gestion-grupos/<int:id_grupo>", methods=["PUT"])
@requiere_permiso("gestionar_grupos")
def actualizar_grupo_gestion(id_grupo):
    valores, error = _validar_datos_grupo(request.get_json(silent=True) or {})
    if error:
        return jsonify({"mensaje": error}), 400
    periodo, codigo, id_asignatura, codigo_asignatura, cupo = valores
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM public.asignaturas a
                JOIN public.programas_academicos p ON p.id_programa=a.id_programa
                WHERE a.id_asignatura=%s AND a.activa=TRUE AND p.activa=TRUE;
            """, (id_asignatura,))
            if cursor.fetchone() is None:
                return jsonify({"mensaje": "La asignatura seleccionada no está disponible."}), 404
            cursor.execute("""
                UPDATE public.grupos
                SET periodo=%s, codigo=%s, id_asignatura=%s,
                    codigo_asignatura=%s, cupo_maximo=%s
                WHERE id_grupo=%s;
            """, (periodo, codigo, id_asignatura, codigo_asignatura, cupo, id_grupo))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "El grupo no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Grupo actualizado correctamente."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al actualizar grupo")
        return jsonify({"mensaje": "No fue posible actualizar el grupo. Verifica que no exista un grupo duplicado para esa asignatura y periodo."}), 500
    finally:
        if conexion is not None:
            conexion.close()


@app.route("/api/gestion-grupos/<int:id_grupo>/estado", methods=["PATCH"])
@requiere_permiso("gestionar_grupos")
def cambiar_estado_grupo_gestion(id_grupo):
    d = request.get_json(silent=True) or {}
    activo = d.get("activo")
    if not isinstance(activo, bool):
        return jsonify({"mensaje": "El estado enviado no es válido."}), 400
    conexion = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE public.grupos SET activo=%s WHERE id_grupo=%s", (activo, id_grupo))
            if cursor.rowcount == 0:
                return jsonify({"mensaje": "El grupo no existe."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Estado del grupo actualizado."}), 200
    except Exception:
        if conexion:
            conexion.rollback()
        app.logger.exception("Error al cambiar estado del grupo")
        return jsonify({"mensaje": "No fue posible actualizar el estado del grupo."}), 500
    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# DATOS INICIALES PARA GESTIÓN DE DOCENTES - HU5
# ======================================================

@app.route("/api/docentes/datos-iniciales", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def obtener_datos_docentes():

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion.cursor() as cursor:

            cursor.execute("""
                SELECT
                    id_usuario,
                    nombres,
                    apellidos,
                    correo
                FROM public.usuarios
                WHERE rol = 'profesor'
                  AND activo = TRUE
                  AND estado_cuenta = 'activo'
                ORDER BY nombres, apellidos;
            """)

            docentes = [
                {
                    "id_usuario": fila[0],
                    "nombres": fila[1],
                    "apellidos": fila[2],
                    "correo": fila[3]
                }
                for fila in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT id_sede, nombre
                FROM public.sedes
                WHERE activa = TRUE
                ORDER BY nombre;
            """)

            sedes = [
                {
                    "id_sede": fila[0],
                    "nombre": fila[1]
                }
                for fila in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT
                    id_franja,
                    nombre,
                    jornada,
                    hora_inicio::text,
                    hora_fin::text
                FROM public.franjas_horarias
                WHERE activa = TRUE
                ORDER BY id_franja;
            """)

            franjas = [
                {
                    "id_franja": fila[0],
                    "nombre": fila[1],
                    "jornada": fila[2],
                    "hora_inicio": fila[3],
                    "hora_fin": fila[4]
                }
                for fila in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT id_asignatura, nombre, semestre
                FROM public.asignaturas
                WHERE activa = TRUE
                ORDER BY semestre, nombre;
            """)

            asignaturas = [
                {
                    "id_asignatura": fila[0],
                    "nombre": fila[1],
                    "semestre": fila[2]
                }
                for fila in cursor.fetchall()
            ]

        return jsonify({
            "mensaje": "Datos consultados correctamente.",
            "docentes": docentes,
            "sedes": sedes,
            "franjas": franjas,
            "asignaturas": asignaturas
        }), 200

    except Exception:
        app.logger.exception(
            "Error al consultar los datos de Gestión de Docentes"
        )

        return jsonify({
            "mensaje": "No fue posible consultar los datos."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# CONSULTAR DISPONIBILIDADES DOCENTES - HU5
# ======================================================

@app.route("/api/docentes/disponibilidades", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def consultar_disponibilidades():

    conexion = None

    docente = request.args.get("docente", "").strip()
    sede = request.args.get("sede", "").strip()
    dia = request.args.get("dia", "").strip()

    try:
        conexion = obtener_conexion()

        consulta = """
            SELECT
                d.id_disponibilidad,
                u.id_usuario,
                u.nombres || ' ' || u.apellidos AS docente,
                d.dia_semana,
                s.id_sede,
                s.nombre AS sede,
                f.id_franja,
                f.nombre AS franja,
                f.jornada,
                f.hora_inicio::text,
                f.hora_fin::text,
                a.id_asignatura,
                COALESCE(a.nombre, 'Sin asignatura') AS asignatura,
                d.disponible
            FROM public.disponibilidad_docente d
            INNER JOIN public.usuarios u
                ON d.id_usuario = u.id_usuario
            INNER JOIN public.sedes s
                ON d.id_sede = s.id_sede
            INNER JOIN public.franjas_horarias f
                ON d.id_franja = f.id_franja
            LEFT JOIN public.asignaturas a
                ON d.id_asignatura = a.id_asignatura
            WHERE u.rol = 'profesor'
              AND u.activo = TRUE
              AND u.estado_cuenta = 'activo'
        """

        parametros = []

        if docente:
            consulta += """
                AND (
                    u.nombres || ' ' || u.apellidos
                ) ILIKE %s
            """
            parametros.append(f"%{docente}%")

        if sede:
            try:
                sede_id = int(sede)
            except ValueError:
                return jsonify({
                    "mensaje": "El filtro de sede no es válido."
                }), 400

            consulta += " AND s.id_sede = %s"
            parametros.append(sede_id)

        if dia:
            consulta += " AND d.dia_semana = %s"
            parametros.append(dia)

        consulta += """
            ORDER BY
                u.nombres,
                u.apellidos,
                CASE d.dia_semana
                    WHEN 'Lunes' THEN 1
                    WHEN 'Martes' THEN 2
                    WHEN 'Miércoles' THEN 3
                    WHEN 'Jueves' THEN 4
                    WHEN 'Viernes' THEN 5
                    WHEN 'Sábado' THEN 6
                    ELSE 7
                END,
                f.hora_inicio;
        """

        with conexion.cursor() as cursor:
            cursor.execute(consulta, tuple(parametros))
            filas = cursor.fetchall()

        disponibilidades = [
            {
                "id_disponibilidad": fila[0],
                "id_usuario": fila[1],
                "docente": fila[2],
                "dia_semana": fila[3],
                "id_sede": fila[4],
                "sede": fila[5],
                "id_franja": fila[6],
                "franja": fila[7],
                "jornada": fila[8],
                "hora_inicio": fila[9],
                "hora_fin": fila[10],
                "id_asignatura": fila[11],
                "asignatura": fila[12],
                "disponible": fila[13]
            }
            for fila in filas
        ]

        return jsonify({
            "disponibilidades": disponibilidades
        }), 200

    except Exception:
        app.logger.exception(
            "Error al consultar disponibilidades docentes"
        )

        return jsonify({
            "mensaje": "No fue posible consultar las disponibilidades."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# REGISTRAR DISPONIBILIDAD DOCENTE - HU5
# ======================================================

@app.route("/api/docentes/disponibilidades", methods=["POST"])
@requiere_permiso("gestionar_docentes")
def registrar_disponibilidad():

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "mensaje": "No se recibieron datos válidos."
        }), 400

    try:
        id_usuario = int(datos.get("id_usuario"))
        id_sede = int(datos.get("id_sede"))
        id_franja = int(datos.get("id_franja"))

        id_asignatura = datos.get("id_asignatura")

        if id_asignatura in (None, ""):
            id_asignatura = None
        else:
            id_asignatura = int(id_asignatura)

    except (TypeError, ValueError):
        return jsonify({
            "mensaje": "Selecciona un docente, una sede y una franja válida."
        }), 400

    dia_semana = str(datos.get("dia_semana", "")).strip()

    dias_permitidos = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado"
    ]

    if dia_semana not in dias_permitidos:
        return jsonify({
            "mensaje": "Selecciona un día válido."
        }), 400

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:

                cursor.execute("""
                    SELECT id_usuario
                    FROM public.usuarios
                    WHERE id_usuario = %s
                      AND rol = 'profesor'
                      AND activo = TRUE
                      AND estado_cuenta = 'activo';
                """, (id_usuario,))

                if not cursor.fetchone():
                    return jsonify({
                        "mensaje": "El docente seleccionado no está autorizado."
                    }), 400

                cursor.execute("""
                    SELECT id_sede
                    FROM public.sedes
                    WHERE id_sede = %s
                      AND activa = TRUE;
                """, (id_sede,))

                if not cursor.fetchone():
                    return jsonify({
                        "mensaje": "La sede seleccionada no está activa."
                    }), 400

                cursor.execute("""
                    SELECT id_franja
                    FROM public.franjas_horarias
                    WHERE id_franja = %s
                      AND activa = TRUE;
                """, (id_franja,))

                if not cursor.fetchone():
                    return jsonify({
                        "mensaje": "La franja horaria seleccionada no está activa."
                    }), 400

                if id_asignatura is not None:
                    cursor.execute("""
                        SELECT id_asignatura
                        FROM public.asignaturas
                        WHERE id_asignatura = %s
                          AND activa = TRUE;
                    """, (id_asignatura,))

                    if not cursor.fetchone():
                        return jsonify({
                            "mensaje": "La asignatura seleccionada no está activa."
                        }), 400

                cursor.execute("""
                    INSERT INTO public.disponibilidad_docente (
                        id_usuario,
                        id_sede,
                        id_franja,
                        id_asignatura,
                        dia_semana,
                        disponible
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    RETURNING id_disponibilidad;
                """, (
                    id_usuario,
                    id_sede,
                    id_franja,
                    id_asignatura,
                    dia_semana
                ))

                id_disponibilidad = cursor.fetchone()[0]

        return jsonify({
            "mensaje": "Disponibilidad registrada correctamente.",
            "id_disponibilidad": id_disponibilidad
        }), 201

    except Exception:
        app.logger.exception(
            "Error al registrar disponibilidad docente"
        )

        return jsonify({
            "mensaje": "No fue posible registrar la disponibilidad."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# CAMBIAR ESTADO DE DISPONIBILIDAD - HU5
# ======================================================

@app.route(
    "/api/docentes/disponibilidades/<int:id_disponibilidad>/estado",
    methods=["PATCH"]
)
@requiere_permiso("gestionar_docentes")
def cambiar_estado_disponibilidad(id_disponibilidad):

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict) or not isinstance(
        datos.get("disponible"), bool
    ):
        return jsonify({
            "mensaje": "El estado enviado no es válido."
        }), 400

    nuevo_estado = datos["disponible"]
    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    UPDATE public.disponibilidad_docente
                    SET disponible = %s
                    WHERE id_disponibilidad = %s
                    RETURNING id_disponibilidad;
                """, (nuevo_estado, id_disponibilidad))

                resultado = cursor.fetchone()

                if not resultado:
                    return jsonify({
                        "mensaje": "No se encontró la disponibilidad."
                    }), 404

        mensaje = (
            "Disponibilidad activada correctamente."
            if nuevo_estado
            else "Disponibilidad desactivada correctamente."
        )

        return jsonify({
            "mensaje": mensaje,
            "disponible": nuevo_estado
        }), 200

    except Exception:
        app.logger.exception(
            "Error al cambiar el estado de disponibilidad"
        )

        return jsonify({
            "mensaje": "No fue posible cambiar el estado."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()



# ======================================================
# CONSULTAR DOCENTES Y ASIGNATURAS - HU6
# ======================================================

@app.route("/api/docentes/hu6", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def consultar_docentes_hu6():
    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT
                    u.id_usuario,
                    u.nombres,
                    u.apellidos,
                    u.correo,
                    u.documento,
                    u.estado_cuenta,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'id_docente_asignatura', da.id_docente_asignatura,
                                'id_asignatura', a.id_asignatura,
                                'nombre', a.nombre,
                                'semestre', a.semestre
                            )
                            ORDER BY a.semestre, a.nombre
                        ) FILTER (WHERE da.id_docente_asignatura IS NOT NULL),
                        '[]'::json
                    ) AS asignaturas
                FROM public.usuarios u
                LEFT JOIN public.docente_asignatura da
                    ON da.id_usuario = u.id_usuario
                LEFT JOIN public.asignaturas a
                    ON a.id_asignatura = da.id_asignatura
                WHERE u.rol = 'profesor'
                  AND u.activo = TRUE
                  AND u.estado_cuenta = 'activo'
                GROUP BY
                    u.id_usuario,
                    u.nombres,
                    u.apellidos,
                    u.correo,
                    u.documento,
                    u.estado_cuenta
                ORDER BY u.nombres, u.apellidos;
            """)

            filas = cursor.fetchall()

        docentes = [
            {
                "id_usuario": fila[0],
                "nombres": fila[1],
                "apellidos": fila[2],
                "correo": fila[3],
                "documento": fila[4],
                "estado_cuenta": fila[5],
                "asignaturas": fila[6]
            }
            for fila in filas
        ]

        return jsonify({"docentes": docentes}), 200

    except Exception:
        app.logger.exception("Error al consultar docentes para HU6")
        return jsonify({
            "mensaje": "No fue posible consultar los docentes."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# EDITAR INFORMACIÓN DEL DOCENTE - HU6
# ======================================================

@app.route("/api/docentes/<int:id_usuario>", methods=["PUT"])
@requiere_permiso("gestionar_docentes")
def editar_docente(id_usuario):
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({"mensaje": "No se recibieron datos válidos."}), 400

    nombres = str(datos.get("nombres", "")).strip()
    apellidos = str(datos.get("apellidos", "")).strip()
    correo = str(datos.get("correo", "")).strip().lower()
    documento = str(datos.get("documento", "")).strip()

    if not all([nombres, apellidos, correo, documento]):
        return jsonify({
            "mensaje": "Completa todos los campos obligatorios."
        }), 400

    if len(nombres) > 100 or len(apellidos) > 100:
        return jsonify({
            "mensaje": "Los nombres o apellidos son demasiado largos."
        }), 400

    if len(correo) > 150 or len(documento) > 30:
        return jsonify({
            "mensaje": "El correo o documento supera la longitud permitida."
        }), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        return jsonify({"mensaje": "Ingresa un correo válido."}), 400

    if not correo.endswith("@profesores.uniajc.edu.co"):
        return jsonify({
            "mensaje": "El correo debe pertenecer al dominio institucional de profesores."
        }), 400

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    UPDATE public.usuarios
                    SET nombres = %s,
                        apellidos = %s,
                        correo = %s,
                        documento = %s,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id_usuario = %s
                      AND rol = 'profesor'
                      AND activo = TRUE
                      AND estado_cuenta = 'activo'
                    RETURNING id_usuario;
                """, (nombres, apellidos, correo, documento, id_usuario))

                actualizado = cursor.fetchone()

                if not actualizado:
                    return jsonify({
                        "mensaje": "No se encontró un docente autorizado para editar."
                    }), 404

        return jsonify({
            "mensaje": "Información del docente actualizada correctamente."
        }), 200

    except Exception as error:
        app.logger.exception("Error al editar información del docente")

        if getattr(error, "sqlstate", None) == "23505":
            return jsonify({
                "mensaje": "El correo o documento ya está registrado por otro usuario."
            }), 409

        return jsonify({
            "mensaje": "No fue posible actualizar la información del docente."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# ASOCIAR ASIGNATURA A DOCENTE - HU6
# ======================================================

@app.route("/api/docentes/<int:id_usuario>/asignaturas", methods=["POST"])
@requiere_permiso("gestionar_docentes")
def asociar_asignatura_docente(id_usuario):
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({"mensaje": "No se recibieron datos válidos."}), 400

    try:
        id_asignatura = int(datos.get("id_asignatura"))
    except (TypeError, ValueError):
        return jsonify({"mensaje": "Selecciona una asignatura válida."}), 400

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT id_usuario
                    FROM public.usuarios
                    WHERE id_usuario = %s
                      AND rol = 'profesor'
                      AND activo = TRUE
                      AND estado_cuenta = 'activo';
                """, (id_usuario,))

                if not cursor.fetchone():
                    return jsonify({
                        "mensaje": "El docente seleccionado no está autorizado."
                    }), 404

                cursor.execute("""
                    SELECT id_asignatura
                    FROM public.asignaturas
                    WHERE id_asignatura = %s
                      AND activa = TRUE;
                """, (id_asignatura,))

                if not cursor.fetchone():
                    return jsonify({
                        "mensaje": "La asignatura seleccionada no está activa."
                    }), 404

                cursor.execute("""
                    INSERT INTO public.docente_asignatura (
                        id_usuario,
                        id_asignatura
                    )
                    VALUES (%s, %s)
                    RETURNING id_docente_asignatura;
                """, (id_usuario, id_asignatura))

                id_docente_asignatura = cursor.fetchone()[0]

        return jsonify({
            "mensaje": "Asignatura asociada correctamente.",
            "id_docente_asignatura": id_docente_asignatura
        }), 201

    except Exception as error:
        app.logger.exception("Error al asociar asignatura al docente")

        if getattr(error, "sqlstate", None) == "23505":
            return jsonify({
                "mensaje": "Esta asignatura ya está asociada a este docente."
            }), 409

        return jsonify({
            "mensaje": "No fue posible asociar la asignatura."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# RETIRAR ASIGNATURA DE DOCENTE - HU6
# ======================================================

@app.route(
    "/api/docentes/asociaciones/<int:id_docente_asignatura>",
    methods=["DELETE"]
)
@requiere_permiso("gestionar_docentes")
def retirar_asignatura_docente(id_docente_asignatura):
    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM public.docente_asignatura
                    WHERE id_docente_asignatura = %s
                    RETURNING id_docente_asignatura;
                """, (id_docente_asignatura,))

                eliminada = cursor.fetchone()

                if not eliminada:
                    return jsonify({
                        "mensaje": "No se encontró la asociación."
                    }), 404

        return jsonify({
            "mensaje": "Asignatura retirada del docente correctamente."
        }), 200

    except Exception:
        app.logger.exception("Error al retirar asignatura del docente")
        return jsonify({
            "mensaje": "No fue posible retirar la asignatura."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# INICIO DE SESIÓN - HU3
# ======================================================

@app.route("/api/login", methods=["POST"])
def iniciar_sesion():

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "mensaje": "Datos de inicio de sesión no válidos."
        }), 400

    correo = str(datos.get("correo", "")).strip().lower()
    contrasena = str(datos.get("contrasena", ""))

    if not correo or not contrasena:
        return jsonify({
            "mensaje": "Ingresa tu correo y contraseña."
        }), 400

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id_usuario,
                    nombres,
                    apellidos,
                    contrasena_hash,
                    rol,
                    activo,
                    estado_cuenta
                FROM public.usuarios
                WHERE LOWER(correo) = %s
                LIMIT 1;
            """, (correo,))

            usuario = cursor.fetchone()

        if not usuario:
            return jsonify({
                "mensaje": "Correo o contraseña incorrectos."
            }), 401

        (
            id_usuario,
            nombres,
            apellidos,
            contrasena_hash,
            rol,
            activo,
            estado_cuenta
        ) = usuario

        if not check_password_hash(contrasena_hash, contrasena):
            return jsonify({
                "mensaje": "Correo o contraseña incorrectos."
            }), 401

        if not activo or estado_cuenta != "activo":
            return jsonify({
                "mensaje": (
                    "Tu cuenta no está activa. "
                    "Si eres profesor, espera la aprobación "
                    "del administrador."
                )
            }), 403

        session.clear()
        session["id_usuario"] = id_usuario
        session["rol"] = rol
        session["nombres"] = nombres
        session["apellidos"] = apellidos

        return jsonify({
            "mensaje": "Inicio de sesión correcto.",
            "usuario": {
                "id_usuario": id_usuario,
                "nombres": nombres,
                "apellidos": apellidos,
                "rol": rol
            }
        }), 200

    except Exception:
        app.logger.exception("Error durante el inicio de sesión")

        return jsonify({
            "mensaje": (
                "No fue posible iniciar sesión. "
                "Inténtalo más tarde."
            )
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# CIERRE DE SESIÓN
# ======================================================

@app.route("/api/logout", methods=["POST"])
def cerrar_sesion():

    session.clear()

    return jsonify({
        "mensaje": "Sesión cerrada correctamente."
    }), 200


# ======================================================
# COMPROBAR CONEXIÓN CON LA BASE DE DATOS
# ======================================================

@app.route("/api/estado-db")
def estado_db():

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            nombre_bd = cursor.fetchone()[0]

        return jsonify({
            "estado": "conectado",
            "base_datos": nombre_bd
        }), 200

    except Exception:
        app.logger.exception("Error al consultar PostgreSQL")

        return jsonify({
            "estado": "error",
            "mensaje": "No se pudo conectar con la base de datos"
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# REGISTRO DE USUARIOS - HU1
# ======================================================

@app.route("/api/registro", methods=["POST"])
def registrar_usuario():

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "mensaje": "No se recibieron datos válidos."
        }), 400

    nombres = str(datos.get("nombres", "")).strip()
    apellidos = str(datos.get("apellidos", "")).strip()
    correo = str(datos.get("correo", "")).strip().lower()
    documento = str(datos.get("documento", "")).strip()
    contrasena = str(datos.get("contrasena", ""))
    rol = str(datos.get("rol", "")).strip().lower()
    acepta_terminos = datos.get("acepta_terminos") is True

    if not all([
        nombres,
        apellidos,
        correo,
        documento,
        contrasena
    ]):
        return jsonify({
            "mensaje": "Completa todos los campos obligatorios."
        }), 400

    if len(nombres) > 100 or len(apellidos) > 100:
        return jsonify({
            "mensaje": "Los nombres o apellidos son demasiado largos."
        }), 400

    if len(correo) > 150 or len(documento) > 30:
        return jsonify({
            "mensaje": (
                "El correo o documento supera "
                "la longitud permitida."
            )
        }), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        return jsonify({
            "mensaje": "Ingresa un correo con formato válido."
        }), 400

    if len(contrasena) < 8:
        return jsonify({
            "mensaje": "La contraseña debe tener al menos 8 caracteres."
        }), 400

    if not acepta_terminos:
        return jsonify({
            "mensaje": (
                "Debes aceptar los términos y "
                "las políticas de privacidad."
            )
        }), 400

    if rol not in DOMINIOS_POR_ROL:
        return jsonify({
            "mensaje": (
                "Ese rol no está habilitado "
                "para el registro público."
            )
        }), 400

    if not correo.endswith(DOMINIOS_POR_ROL[rol]):
        return jsonify({
            "mensaje": (
                "El correo no corresponde al dominio "
                "institucional del rol seleccionado."
            )
        }), 400

    estado_cuenta = (
        "activo" if rol == "estudiante" else "pendiente"
    )

    contrasena_hash = generate_password_hash(contrasena)
    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.usuarios (
                        nombres,
                        apellidos,
                        correo,
                        documento,
                        contrasena_hash,
                        rol,
                        acepta_terminos,
                        activo,
                        estado_cuenta
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, TRUE, %s
                    )
                    RETURNING id_usuario;
                """, (
                    nombres,
                    apellidos,
                    correo,
                    documento,
                    contrasena_hash,
                    rol,
                    acepta_terminos,
                    estado_cuenta
                ))

                id_usuario = cursor.fetchone()[0]

        if rol == "estudiante":
            mensaje = (
                "Tu cuenta fue creada correctamente. "
                "Ya puedes ingresar."
            )
        else:
            mensaje = (
                "Tu solicitud fue recibida. "
                "Tu cuenta quedará pendiente hasta que "
                "un administrador la autorice."
            )

        return jsonify({
            "mensaje": mensaje,
            "estado_cuenta": estado_cuenta,
            "id_usuario": id_usuario
        }), 201

    except Exception as error:
        app.logger.exception("Error al registrar usuario")

        if getattr(error, "sqlstate", None) == "23505":
            return jsonify({
                "mensaje": (
                    "Ya existe una cuenta con ese "
                    "correo o documento."
                )
            }), 409

        return jsonify({
            "mensaje": (
                "No fue posible crear la cuenta. "
                "Inténtalo más tarde."
            )
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# ======================================================
# VERIFICAR PERMISOS - HU2
# ======================================================

@app.route("/api/prueba-permiso-docentes", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def prueba_permiso_docentes():

    return jsonify({
        "mensaje": "Permiso verificado correctamente.",
        "permiso": "gestionar_docentes"
    }), 200


# ======================================================
# EJECUCIÓN DE LA APLICACIÓN
# ======================================================

if __name__ == "__main__":
    app.run(debug=True)
