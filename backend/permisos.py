
from functools import wraps

from flask import jsonify, request, g
from config.database import obtener_conexion


def requiere_permiso(codigo_permiso):
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            id_usuario = request.headers.get("X-Usuario-ID")

            if not id_usuario or not id_usuario.isdigit():
                return jsonify({
                    "mensaje": "Debes identificarte para realizar esta operación."
                }), 401

            conexion = None

            try:
                conexion = obtener_conexion()

                with conexion.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM public.usuarios u
                            JOIN public.roles r
                                ON r.codigo = u.rol
                            JOIN public.rol_permiso rp
                                ON rp.id_rol = r.id_rol
                            JOIN public.permisos p
                                ON p.id_permiso = rp.id_permiso
                            WHERE u.id_usuario = %s
                              AND u.activo = TRUE
                              AND u.estado_cuenta = 'activo'
                              AND p.codigo = %s
                        );
                        """,
                        (int(id_usuario), codigo_permiso)
                    )

                    autorizado = cursor.fetchone()[0]

                if not autorizado:
                    return jsonify({
                        "mensaje": "No tienes permiso para realizar esta operación."
                    }), 403

                g.id_usuario = int(id_usuario)
                return funcion(*args, **kwargs)

            except Exception:
                return jsonify({
                    "mensaje": "No fue posible verificar los permisos."
                }), 500

            finally:
                if conexion is not None:
                    conexion.close()

        return envoltura

    return decorador
