
from config.database import obtener_conexion

try:
    conexion = obtener_conexion()
    print("¡Conexión exitosa con PostgreSQL!")

    with conexion.cursor() as cursor:
        cursor.execute("SELECT current_database();")
        resultado = cursor.fetchone()
        print("Base de datos conectada:", resultado[0])

    conexion.close()

except Exception as error:
    print("Error al conectar con PostgreSQL:")
    print(error)
