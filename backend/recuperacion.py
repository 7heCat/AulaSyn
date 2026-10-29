"""
HU4 · Recuperación y cambio de contraseña.

  POST /api/recuperacion/solicitar  {correo}                      -> envía código
  POST /api/recuperacion/verificar  {correo, codigo}              -> valida sin consumir
  POST /api/recuperacion/restablecer {correo, codigo, contrasena} -> cambia la clave

Seguridad: código de 6 dígitos hasheado (HMAC), vence en 15 min, un solo uso,
máx. 5 intentos, 60 s entre solicitudes y 5 por hora, respuesta genérica en
"solicitar" (no revela si el correo existe).
"""
import hmac
import hashlib
import os
import re
import secrets

import psycopg
from flask import Blueprint, current_app, jsonify, request
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

from config.database import obtener_conexion
from correo import enviar_codigo_recuperacion

recuperacion_bp = Blueprint("recuperacion", __name__)

# --- Nombres de la tabla (ajustar aquí si tu tabla real difiere) ---
TABLA = "public.recuperacion_contrasena"
C_USUARIO, C_HASH, C_EXPIRA = "id_usuario", "codigo_hash", "fecha_expiracion"
C_USADO, C_CREADO, C_INTENTOS, C_ID = "utilizado", "fecha_creacion", "intentos", "id_recuperacion"

MINUTOS_VIGENCIA = 15
MAX_INTENTOS = 5
ESPERA_SEGUNDOS = 60
MAX_POR_HORA = 5

MSG_GENERICO = "Si el correo está registrado, recibirás un código de verificación."
MSG_CODIGO = "El código es incorrecto o ha vencido."


def _err(msg, cod):
    return jsonify({"mensaje": msg}), cod


def _hash(id_usuario, codigo):
    clave = (os.getenv("FLASK_SECRET_KEY") or "dev").encode()
    return hmac.new(clave, f"{id_usuario}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _datos():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def _texto(d, k):
    v = d.get(k)
    return v.strip() if isinstance(v, str) else ""


def contrasena_valida(c):
    """Devuelve mensaje de error o None."""
    if len(c) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if len(c) > 128:
        return "La contraseña es demasiado larga."
    if not re.search(r"[A-Za-z]", c) or not re.search(r"\d", c):
        return "La contraseña debe incluir al menos una letra y un número."
    return None


def _usuario_por_correo(cur, correo, bloquear=False):
    cur.execute(
        "SELECT id_usuario, nombres, correo FROM public.usuarios "
        "WHERE lower(correo) = %s AND activo IS TRUE AND estado_cuenta = 'activo'"
        + (" FOR UPDATE" if bloquear else ""),
        (correo.lower(),),
    )
    return cur.fetchone()


def _validar_codigo(cur, usuario, codigo):
    """Con el usuario bloqueado. Cuenta el intento. Devuelve (ok, fila)."""
    cur.execute(
        f"SELECT {C_ID} AS id, {C_HASH} AS h, {C_INTENTOS} AS intentos FROM {TABLA} "
        f"WHERE {C_USUARIO} = %s AND {C_USADO} IS FALSE AND {C_EXPIRA} > now() "
        f"ORDER BY {C_CREADO} DESC LIMIT 1 FOR UPDATE",
        (usuario["id_usuario"],),
    )
    fila = cur.fetchone()
    if fila is None or fila["intentos"] >= MAX_INTENTOS:
        return False, None
    if hmac.compare_digest(fila["h"], _hash(usuario["id_usuario"], codigo)):
        return True, fila
    cur.execute(f"UPDATE {TABLA} SET {C_INTENTOS} = {C_INTENTOS} + 1 WHERE {C_ID} = %s", (fila["id"],))
    return False, None


@recuperacion_bp.route("/api/recuperacion/solicitar", methods=["POST"])
def solicitar():
    correo = _texto(_datos(), "correo").lower()
    if not correo or len(correo) > 254 or "@" not in correo:
        return _err("Ingresa un correo válido.", 400)

    envio = None
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            u = _usuario_por_correo(cur, correo, bloquear=True)
            if u:
                cur.execute(
                    f"SELECT count(*) FILTER (WHERE {C_CREADO} > now() - interval '1 hour') AS hora, "
                    f"count(*) FILTER (WHERE {C_CREADO} > now() - make_interval(secs => %s)) AS reciente "
                    f"FROM {TABLA} WHERE {C_USUARIO} = %s",
                    (ESPERA_SEGUNDOS, u["id_usuario"]),
                )
                c = cur.fetchone()
                if c["reciente"] == 0 and c["hora"] < MAX_POR_HORA:
                    codigo = f"{secrets.randbelow(10**6):06d}"
                    cur.execute(f"UPDATE {TABLA} SET {C_USADO} = TRUE WHERE {C_USUARIO} = %s AND {C_USADO} IS FALSE",
                                (u["id_usuario"],))
                    cur.execute(
                        f"INSERT INTO {TABLA} ({C_USUARIO}, {C_HASH}, {C_EXPIRA}) "
                        "VALUES (%s, %s, now() + make_interval(mins => %s))",
                        (u["id_usuario"], _hash(u["id_usuario"], codigo), MINUTOS_VIGENCIA),
                    )
                    envio = (u["correo"], u["nombres"], codigo)
    except psycopg.Error:
        current_app.logger.exception("Error en solicitud de recuperación")
        return _err("No fue posible procesar la solicitud. Inténtalo más tarde.", 500)

    if envio:  # después del commit
        enviar_codigo_recuperacion(*envio, MINUTOS_VIGENCIA, debug=current_app.debug)
    return jsonify({"mensaje": MSG_GENERICO})


@recuperacion_bp.route("/api/recuperacion/verificar", methods=["POST"])
def verificar():
    d = _datos()
    correo, codigo = _texto(d, "correo"), _texto(d, "codigo")
    if not correo or not re.fullmatch(r"\d{6}", codigo):
        return _err(MSG_CODIGO, 400)
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            u = _usuario_por_correo(cur, correo, bloquear=True)
            ok = bool(u) and _validar_codigo(cur, u, codigo)[0]
    except psycopg.Error:
        current_app.logger.exception("Error al verificar código")
        return _err("No fue posible procesar la solicitud. Inténtalo más tarde.", 500)
    return jsonify({"mensaje": "Código verificado."}) if ok else _err(MSG_CODIGO, 400)


@recuperacion_bp.route("/api/recuperacion/restablecer", methods=["POST"])
def restablecer():
    d = _datos()
    correo, codigo = _texto(d, "correo"), _texto(d, "codigo")
    nueva = d.get("contrasena") if isinstance(d.get("contrasena"), str) else ""
    if not correo or not re.fullmatch(r"\d{6}", codigo):
        return _err(MSG_CODIGO, 400)
    error = contrasena_valida(nueva)
    if error:
        return _err(error, 400)
    try:
        with obtener_conexion() as con, con.cursor(row_factory=dict_row) as cur:
            u = _usuario_por_correo(cur, correo, bloquear=True)
            ok, fila = _validar_codigo(cur, u, codigo) if u else (False, None)
            if ok:
                cur.execute(f"UPDATE {TABLA} SET {C_USADO} = TRUE WHERE {C_USUARIO} = %s", (u["id_usuario"],))
                cur.execute(
                    "UPDATE public.usuarios SET contrasena_hash = %s, fecha_actualizacion = CURRENT_TIMESTAMP "
                    "WHERE id_usuario = %s",
                    (generate_password_hash(nueva), u["id_usuario"]),
                )
    except psycopg.Error:
        current_app.logger.exception("Error al restablecer contraseña")
        return _err("No fue posible procesar la solicitud. Inténtalo más tarde.", 500)
    if not ok:
        return _err(MSG_CODIGO, 400)
    return jsonify({"mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."})
