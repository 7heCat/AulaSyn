
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
