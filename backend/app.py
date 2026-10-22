from flask import Flask, jsonify, render_template, request
from config.database import obtener_conexion
from werkzeug.security import generate_password_hash
import re

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)

# Dominios permitidos para el registro público.
DOMINIOS_POR_ROL = {
    "estudiante": "@estudiante.uniajc.edu.co",
    "profesor": "@profesores.uniajc.edu.co"
}


@app.route("/")
def inicio():
    return render_template("autenticacion.html")


@app.route("/api/estado-db")
def estado_db():
    try:
        conexion = obtener_conexion()

        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT current_database();")
                nombre_bd = cursor.fetchone()[0]
        finally:
            conexion.close()

        return jsonify({
            "estado": "conectado",
            "base_datos": nombre_bd
        })

    except Exception:
        app.logger.exception("Error al consultar PostgreSQL")

        return jsonify({
            "estado": "error",
            "mensaje": "No se pudo conectar con la base de datos"
        }), 500


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
    if not all([nombres, apellidos, correo, documento, contrasena]):
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
        return jsonify({
            "mensaje": "Ingresa un correo con formato válido."
        }), 400

    if len(contrasena) < 8:
        return jsonify({
            "mensaje": "La contraseña debe tener al menos 8 caracteres."
        }), 400

    if not acepta_terminos:
        return jsonify({
            "mensaje": "Debes aceptar los términos y las políticas de privacidad."
        }), 400

    # El servidor no permite registrar coordinadores públicamente.
    if rol not in DOMINIOS_POR_ROL:
        return jsonify({
            "mensaje": "Ese rol no está habilitado para el registro público."
        }), 400

    # Verificar que el correo corresponda al rol elegido.
    if not correo.endswith(DOMINIOS_POR_ROL[rol]):
        return jsonify({
            "mensaje": "El correo no corresponde al dominio institucional del rol seleccionado."
        }), 400

    # Los estudiantes quedan activos y los profesores pendientes.
    estado_cuenta = "activo" if rol == "estudiante" else "pendiente"

    # Nunca guardar la contraseña directamente.
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
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
                "un coordinador la autorice."
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
                "mensaje": "Ya existe una cuenta con ese correo o documento."
            }), 409

        return jsonify({
            "mensaje": "No fue posible crear la cuenta. Inténtalo más tarde."
        }), 500

    finally:
        if conexion is not None:
            conexion.close()



if __name__ == "__main__":
    app.run(debug=True)