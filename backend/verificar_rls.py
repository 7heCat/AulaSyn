
from config.database import obtener_conexion

try:
    conexion = obtener_conexion()

    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT
                current_user,
                session_user,
                rolbypassrls
            FROM pg_roles
            WHERE rolname = current_user;
        """)

        resultado = cursor.fetchone()

        print("\n--- VERIFICACION DE CONEXION ---")
        print("Usuario actual:", resultado[0])
        print("Usuario de sesion:", resultado[1])
        print("Puede omitir RLS:", resultado[2])

    conexion.close()

except Exception as error:
    print("Error al verificar la conexion:", error)
