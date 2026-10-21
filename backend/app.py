
from flask import Flask, jsonify, render_template
from config.database import obtener_conexion

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)

@app.route("/")
def inicio():
    return render_template("autenticacion.html")

@app.route("/api/estado-db")
def estado_db():
    try:
        conexion = obtener_conexion()

        with conexion.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            nombre_bd = cursor.fetchone()[0]

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

if __name__ == "__main__":
    app.run(debug=True)
