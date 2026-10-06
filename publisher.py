"""
Publisher automático de PublishFlow.
Se ejecuta desde GitHub Actions 3 veces al día.
Busca posts programados para la hora actual y los publica.
"""
import os
import io
import re
import json
import time
import base64
import datetime as dt
import requests
from PIL import Image, ImageDraw, ImageFont

DATA = "data"
PLAN_PATH = os.path.join(DATA, "plan_publicacion.json")
REGISTRO_PATH = os.path.join(DATA, "registro_auto.json")
PIEZAS_DIR = os.path.join(DATA, "piezas")

MARCAS = {
    "AdeskCharts": {"prefijo": "ADESK", "color": "#1E4FD8"},
    "SoundSnip Studio PRO": {"prefijo": "SOUNDSNIP", "color": "#6D28D9"},
    "PublishFlow": {"prefijo": "PUBLISHFLOW", "color": "#0F766E"},
}


# --- Utilidades JSON ---
def leer_json(path, defecto):
    if not os.path.exists(path):
        return defecto
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defecto


def escribir_json(path, datos):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _fuente(tam):
    for n in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(n, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def crear_pieza_simple(gancho, color_hex, tamano=(1080, 1080)):
    """Genera una pieza simple (fondo color + gancho centrado)."""
    w, h = tamano
    rgb = _hex_rgb(color_hex)
    img = Image.new("RGB", tamano, rgb)
    if gancho:
        draw = ImageDraw.Draw(img)
        fuente = _fuente(int(w * 0.07))
        palabras, lineas, actual = gancho.split(), [], ""
        for p in palabras:
            prueba = f"{actual} {p}".strip()
            if draw.textlength(prueba, font=fuente) <= w * 0.88:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        if actual:
            lineas.append(actual)
        alto = int(fuente.size * 1.25)
        y = (h - alto * len(lineas)) // 2
        for lin in lineas[:3]:
            ancho = draw.textlength(lin, font=fuente)
            draw.text(((w-ancho)/2, y), lin, font=fuente, fill=(255, 255, 255))
            y += alto
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def cargar_pieza(post):
    """Si hay una pieza guardada en disco, la devuelve. Si no, la genera."""
    ruta = post.get("pieza_path")
    if ruta and os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return f.read()
    color = MARCAS.get(post.get("marca"), {}).get("color", "#7C3AED")
    return crear_pieza_simple(post.get("gancho", ""), color)


# --- Credenciales por marca (desde env vars) ---
def cred_marca(marca):
    prefijo = MARCAS.get(marca, {}).get("prefijo") or re.sub(r"[^A-Z0-9]", "", marca.upper())[:15]
    out = {}
    for k, v in os.environ.items():
        k_up = k.upper()
        if k_up.startswith(prefijo + "_"):
            out[k_up[len(prefijo)+1:]] = v
    return out


# --- Publicadores ---
def _telegram(texto, titulo, imagen, c):
    r = requests.post(
        f"https://api.telegram.org/bot{c['TELEGRAM_BOT_TOKEN']}/sendPhoto",
        data={"chat_id": c["TELEGRAM_CHAT_ID"], "caption": texto[:1024]},
        files={"photo": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description", "Telegram rechazó"))
    chat = str(c["TELEGRAM_CHAT_ID"])
    mid = r["result"]["message_id"]
    return f"https://t.me/{chat[1:]}/{mid}" if chat.startswith("@") else "ok"


def _bluesky(texto, titulo, imagen, c):
    base = "https://bsky.social/xrpc/"
    s = requests.post(base + "com.atproto.server.createSession",
                      json={"identifier": c["BLUESKY_HANDLE"],
                            "password": c["BLUESKY_APP_PASSWORD"]}, timeout=30).json()
    if "accessJwt" not in s:
        raise RuntimeError(s.get("message", "Bluesky: login fallido"))
    cab = {"Authorization": f"Bearer {s['accessJwt']}"}
    blob = requests.post(base + "com.atproto.repo.uploadBlob",
                         headers={**cab, "Content-Type": "image/jpeg"},
                         data=imagen, timeout=60).json()
    texto = texto if len(texto) <= 300 else texto[:299] + "…"
    post = {
        "$type": "app.bsky.feed.post", "text": texto,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images",
                  "images": [{"alt": texto[:200], "image": blob["blob"]}]},
    }
    r = requests.post(base + "com.atproto.repo.createRecord", headers=cab,
                      json={"repo": s["did"], "collection": "app.bsky.feed.post",
                            "record": post}, timeout=30).json()
    return f"https://bsky.app/profile/{s['handle']}/post/{r['uri'].split('/')[-1]}"


def _discord(texto, titulo, imagen, c):
    requests.post(c["DISCORD_WEBHOOK_URL"], params={"wait": "true"},
                  data={"payload_json": json.dumps({"content": texto[:2000]})},
                  files={"files[0]": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60)
    return "ok"


def _mastodon(texto, titulo, imagen, c):
    base = c["MASTODON_URL"].rstrip("/")
    cab = {"Authorization": f"Bearer {c['MASTODON_TOKEN']}"}
    media = requests.post(f"{base}/api/v2/media", headers=cab,
                          files={"file": ("pieza.jpg", imagen, "image/jpeg")},
                          data={"description": (titulo or texto)[:200]}, timeout=60).json()
    for _ in range(10):
        if media.get("url"):
            break
        time.sleep(2)
        media = requests.get(f"{base}/api/v1/media/{media['id']}", headers=cab, timeout=20).json()
    r = requests.post(f"{base}/api/v1/statuses", headers=cab,
                      data={"status": texto[:500], "media_ids[]": media["id"]}, timeout=30).json()
    return r.get("url", "ok")


def _facebook(texto, titulo, imagen, c):
    g = f"https://graph.facebook.com/{c.get('FB_GRAPH_VERSION') or 'v23.0'}"
    r = requests.post(f"{g}/{c['FB_PAGE_ID']}/photos",
                      data={"message": texto, "access_token": c["FB_PAGE_TOKEN"]},
                      files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                      timeout=60).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message", "FB error"))
    return f"https://www.facebook.com/{r.get('post_id', r.get('id'))}"


def _instagram(texto, titulo, imagen, c):
    g = f"https://graph.facebook.com/{c.get('FB_GRAPH_VERSION') or 'v23.0'}"
    tok, ig = c["FB_PAGE_TOKEN"], c["IG_USER_ID"]
    # Alojar en FB
    foto = requests.post(f"{g}/{c['FB_PAGE_ID']}/photos",
                         data={"published": "false", "access_token": tok},
                         files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                         timeout=60).json()
    info = requests.get(f"{g}/{foto['id']}",
                        params={"fields": "images", "access_token": tok}, timeout=20).json()
    url = info["images"][0]["source"]
    # Crear contenedor IG
    cont = requests.post(f"{g}/{ig}/media",
                         data={"image_url": url, "caption": texto, "access_token": tok},
                         timeout=60).json()
    for _ in range(15):
        estado = requests.get(f"{g}/{cont['id']}",
                              params={"fields": "status_code", "access_token": tok},
                              timeout=20).json()
        if estado.get("status_code") == "FINISHED":
            break
        time.sleep(2)
    pub = requests.post(f"{g}/{ig}/media_publish",
                        data={"creation_id": cont["id"], "access_token": tok},
                        timeout=60).json()
    return f"https://www.instagram.com/p/{pub.get('id', '')}/"


def _wordpress(texto, titulo, imagen, c):
    base = c["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
    auth = (c["WP_USER"], c["WP_APP_PASSWORD"])
    media = requests.post(f"{base}/media", auth=auth, data=imagen, timeout=60, headers={
        "Content-Disposition": 'attachment; filename="pieza.jpg"',
        "Content-Type": "image/jpeg"}).json()
    r = requests.post(f"{base}/posts", auth=auth, timeout=30, json={
        "title": titulo or "Novedades",
        "content": texto, "status": "publish",
        "featured_media": media.get("id")}).json()
    return r.get("link", "ok")


PUBLICADORES = {
    "Telegram": _telegram,
    "Bluesky": _bluesky,
    "Discord": _discord,
    "Mastodon": _mastodon,
    "Facebook": _facebook,
    "Instagram": _instagram,
    "WordPress": _wordpress,
    # Añade aquí más según los vayas necesitando (copiando de app.py)
}


# --- Lógica principal ---
def main():
    print(f"🤖 Publisher · {dt.datetime.now().isoformat(timespec='seconds')}")

    plan = leer_json(PLAN_PATH, {"campanas": []})
    campanas = plan.get("campanas", [])
    if not campanas:
        print("📭 No hay campañas programadas.")
        return

    ahora = dt.datetime.now()
    margen_min = 15  # publica si la hora programada está a menos de 15 min de ahora

    publicados = 0
    fallidos = 0
    registro = leer_json(REGISTRO_PATH, [])

    for camp in campanas:
        if camp.get("estado") != "aprobada":
            continue
        for post in camp.get("posts", []):
            if post.get("estado") != "pendiente":
                continue
            try:
                fecha = dt.datetime.fromisoformat(post["fecha_programada"])
            except (KeyError, ValueError):
                continue
            delta = (fecha - ahora).total_seconds() / 60
            if not (-margen_min <= delta <= margen_min):
                continue

            marca = post.get("marca", camp.get("marca"))
            red = post.get("red")
            cred = cred_marca(marca)
            publicador = PUBLICADORES.get(red)

            entrada_reg = {
                "fecha": ahora.isoformat(timespec="seconds"),
                "campana_id": camp.get("id"),
                "post_id": post.get("id"),
                "marca": marca, "red": red,
                "estado": "pendiente", "enlace": "", "error": "",
            }

            if not publicador:
                entrada_reg["estado"] = "error"
                entrada_reg["error"] = f"Sin publicador para {red}"
                fallidos += 1
            elif not cred:
                entrada_reg["estado"] = "error"
                entrada_reg["error"] = f"Sin credenciales para {marca}"
                fallidos += 1
            else:
                try:
                    imagen = cargar_pieza(post)
                    enlace = publicador(post.get("texto", ""),
                                        post.get("titulo", ""), imagen, cred)
                    entrada_reg["estado"] = "publicado"
                    entrada_reg["enlace"] = enlace
                    post["estado"] = "publicado"
                    post["enlace_publicado"] = enlace
                    publicados += 1
                    print(f"  ✅ {marca} / {red} → {enlace}")
                except Exception as e:
                    entrada_reg["estado"] = "error"
                    entrada_reg["error"] = str(e)[:200]
                    post["intentos"] = post.get("intentos", 0) + 1
                    post["ultimo_error"] = str(e)[:200]
                    if post["intentos"] >= 3:
                        post["estado"] = "error_definitivo"
                    fallidos += 1
                    print(f"  ❌ {marca} / {red}: {e}")

            registro.append(entrada_reg)
            time.sleep(1)

    # Guardar todo
    escribir_json(PLAN_PATH, plan)
    escribir_json(REGISTRO_PATH, registro[-1000:])  # últimos 1000

    print(f"✅ {publicados} publicados · ❌ {fallidos} fallidos")


if __name__ == "__main__":
    main()
