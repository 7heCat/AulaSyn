
from config.database import obtener_conexion

try:
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'usuarios',
                      'recuperacion_contrasena'
                  )
                ORDER BY table_name;
            """)

            tablas = cursor.fetchall()

            print("Conexión exitosa con Supabase.")
            print("Tablas encontradas:")

            for tabla in tablas:
                print("-", tabla[0])

except Exception as error:
    print("Error al consultar las tablas:")
    print(error)
