
import os
import re

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session
)

from config.database import obtener_conexion

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from permisos import requiere_permiso


app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)


# Configuración de seguridad de las sesiones.
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# En desarrollo local con HTTP.
# Al desplegar AulaSyn con HTTPS, cambiar a True.
app.config["SESSION_COOKIE_SECURE"] = False


# Dominios permitidos para el registro público.
DOMINIOS_POR_ROL = {
    "estudiante": "@estudiante.uniajc.edu.co",
    "profesor": "@profesores.uniajc.edu.co"
}


@app.route("/")
def inicio():
    return render_template("autenticacion.html")


# INICIO DE SESIÓN
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
            cursor.execute(
                """
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
                """,
                (correo,)
            )

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

        if not check_password_hash(
            contrasena_hash,
            contrasena
        ):
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

        # Crear una nueva sesión después de validar la cuenta.
        session.clear()
        session["id_usuario"] = id_usuario
        session["rol"] = rol

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
        app.logger.exception(
            "Error durante el inicio de sesión"
        )

        return jsonify({
            "mensaje": (
                "No fue posible iniciar sesión. "
                "Inténtalo más tarde."
            )
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# CIERRE DE SESIÓN
@app.route("/api/logout", methods=["POST"])
def cerrar_sesion():
    session.clear()

    return jsonify({
        "mensaje": "Sesión cerrada correctamente."
    }), 200


# COMPROBAR CONEXIÓN CON LA BASE DE DATOS
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
        app.logger.exception(
            "Error al consultar PostgreSQL"
        )

        return jsonify({
            "estado": "error",
            "mensaje": "No se pudo conectar con la base de datos"
        }), 500

    finally:
        if conexion is not None:
            conexion.close()


# REGISTRO DE USUARIOS
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

    # Validar campos obligatorios.
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

    # Validar el formato del correo.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        return jsonify({
            "mensaje": "Ingresa un correo con formato válido."
        }), 400

    if len(contrasena) < 8:
        return jsonify({
            "mensaje": (
                "La contraseña debe tener al menos 8 caracteres."
            )
        }), 400

    if not acepta_terminos:
        return jsonify({
            "mensaje": (
                "Debes aceptar los términos y "
                "las políticas de privacidad."
            )
        }), 400

    # No permitir el registro público de coordinadores.
    if rol not in DOMINIOS_POR_ROL:
        return jsonify({
            "mensaje": (
                "Ese rol no está habilitado "
                "para el registro público."
            )
        }), 400

    # Verificar el dominio institucional correspondiente al rol.
    if not correo.endswith(DOMINIOS_POR_ROL[rol]):
        return jsonify({
            "mensaje": (
                "El correo no corresponde al dominio "
                "institucional del rol seleccionado."
            )
        }), 400

    # Los estudiantes quedan activos y los profesores pendientes.
    estado_cuenta = (
        "activo" if rol == "estudiante" else "pendiente"
    )

    # Guardar la contraseña mediante un hash seguro.
    contrasena_hash = generate_password_hash(contrasena)

    conexion = None

    try:
        conexion = obtener_conexion()

        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
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
                    """,
                    (
                        nombres,
                        apellidos,
                        correo,
                        documento,
                        contrasena_hash,
                        rol,
                        acepta_terminos,
                        estado_cuenta
                    )
                )

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

        # Correo o documento duplicado.
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


# Ruta temporal para comprobar los permisos de HU2.
@app.route("/api/prueba-permiso-docentes", methods=["GET"])
@requiere_permiso("gestionar_docentes")
def prueba_permiso_docentes():
    return jsonify({
        "mensaje": "Permiso verificado correctamente.",
        "permiso": "gestionar_docentes"
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
