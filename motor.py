"""
Motor de la agencia PublishFlow.
  - Equipo y configuración de marcas y redes
  - Trabajo de cada especialista con Gemini
  - Piezas visuales con Pillow
  - Conectores de publicación (Telegram, Bluesky, Facebook)
  - Pack de descarga para subida manual
"""
import io
import json
import re
import time
import zipfile
import datetime as dt

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from google.genai import types
from google.genai.errors import APIError

# -------------------------------------------------------------------
# EQUIPO
# -------------------------------------------------------------------
EQUIPO = [
    {"id": "estrategia", "nombre": "Elena Navarro Ruiz", "rol": "Directora de Estrategia",
     "icono": "🧭", "bio": "Decide mercados, público, redes y horarios de cada campaña."},
    {"id": "copy", "nombre": "Marcos Vidal Herrera", "rol": "Copywriter Senior",
     "icono": "✍️", "bio": "Escribe los textos de cada red, los ganchos y los hashtags."},
    {"id": "creativa", "nombre": "Lucía Ortega Blanco", "rol": "Directora Creativa",
     "icono": "🎨", "bio": "Adapta tus imágenes a cada formato y escribe los guiones de vídeo."},
    {"id": "community", "nombre": "Daniel Soto Morales", "rol": "Community Manager",
     "icono": "📅", "bio": "Publica en las redes conectadas y prepara las descargas del resto."},
    {"id": "analista", "nombre": "Sara Méndez Castillo", "rol": "Analista de Resultados",
     "icono": "📈", "bio": "Sigue cada publicación y te dice qué funciona y qué no."},
    {"id": "talento", "nombre": "Javier Romero Gil", "rol": "Ojeador de Talento",
     "icono": "🤝", "bio": "Encuentra creadores y profesionales para colaborar con tus marcas."},
]
EQ = {m["id"]: m for m in EQUIPO}

MARCAS = {
    "AdeskCharts": {
        "descripcion": ("Plataforma web de trading con screener de acciones y agentes de IA que "
                        "analizan las acciones filtradas. Mejor servicio por menos dinero. "
                        "Suscripción de pago."),
        "url": "https://adeskcharts.com",
        "color": "#1E4FD8",
    },
    "SoundSnip Studio PRO": {
        "descripcion": ("Web de herramientas de audio: controlador DJ, mesa de estudio, efectos y "
                        "editor. Para DJs, productores y creadores. Suscripción de pago."),
        "url": "",
        "color": "#6D28D9",
    },
    "Otra marca": {"descripcion": "", "url": "", "color": "#0F766E"},
}

# tipo: auto = publicación directa · proxima = se conectará más adelante · manual = descarga
REDES = {
    "Telegram":       {"tamano": (1080, 1080), "limite": 1024, "tipo": "auto"},
    "Bluesky":        {"tamano": (1200, 675),  "limite": 300,  "tipo": "auto"},
    "Facebook":       {"tamano": (1080, 1350), "limite": 5000, "tipo": "auto"},
    "Instagram":      {"tamano": (1080, 1350), "limite": 2200, "tipo": "proxima"},
    "Threads":        {"tamano": (1080, 1350), "limite": 500,  "tipo": "proxima"},
    "LinkedIn":       {"tamano": (1200, 627),  "limite": 3000, "tipo": "proxima"},
    "Pinterest":      {"tamano": (1000, 1500), "limite": 500,  "tipo": "proxima"},
    "YouTube Shorts": {"tamano": (1080, 1920), "limite": 5000, "tipo": "proxima"},
    "X (Twitter)":    {"tamano": (1600, 900),  "limite": 280,  "tipo": "manual"},
    "TikTok":         {"tamano": (1080, 1920), "limite": 2200, "tipo": "manual"},
    "WhatsApp":       {"tamano": (1080, 1080), "limite": 1000, "tipo": "manual"},
}

TIPOS = {
    "auto": "Publicación directa",
    "proxima": "Conexión directa próximamente. De momento, descarga y sube",
    "manual": "Subida manual: descarga imagen y texto",
}

SECRETS_RED = {
    "Telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "Bluesky": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
    "Facebook": ["FB_PAGE_ID", "FB_PAGE_TOKEN"],
}


def conectado(red, secretos):
    claves = SECRETS_RED.get(red)
    return bool(claves) and all(secretos.get(k) for k in claves)


# -------------------------------------------------------------------
# IA (Gemini)
# -------------------------------------------------------------------
def _parse_json(texto):
    limpio = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        i, j = limpio.find("{"), limpio.rfind("}")
        if i != -1 and j != -1:
            return json.loads(limpio[i:j + 1])
        raise ValueError("La respuesta de la IA no tenía un formato válido.")


def llamar_ia(client, modelos, contents, json_mode=False, intentos=2):
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    ultimo = None
    for modelo in modelos:
        for k in range(intentos):
            try:
                r = client.models.generate_content(model=modelo, contents=contents, config=config)
                if r and r.text:
                    return _parse_json(r.text) if json_mode else r.text
            except APIError as e:
                ultimo = e
                if getattr(e, "code", None) in (400, 404):
                    break
                time.sleep(2 * (k + 1))
            except (ValueError, json.JSONDecodeError) as e:
                ultimo = e
            except Exception as e:
                ultimo = e
                time.sleep(2 * (k + 1))
    raise ultimo or RuntimeError("No se obtuvo respuesta de la IA.")


def _brief_txt(b):
    return (f"MARCA: {b['marca']}\nPRODUCTO: {b['descripcion']}\nWEB: {b['url'] or '(sin web)'}\n"
            f"OBJETIVO: {b['objetivo']}\nMERCADO: {b['mercado']}\n"
            f"PÚBLICO INDICADO: {b['publico'] or '(decídelo tú)'}\n"
            f"OFERTA / LLAMADA A LA ACCIÓN: {b['oferta'] or '(ninguna concreta)'}")


def crear_estrategia(client, modelos, brief, redes, idioma, fotos_bytes=None):
    """Elena Navarro: mercados, público, redes, horarios y plan semanal."""
    prompt = f"""
Eres {EQ['estrategia']['nombre']}, {EQ['estrategia']['rol']} de una agencia de marketing digital.
Analiza este encargo{" y las imágenes adjuntas" if fotos_bytes else ""}.

{_brief_txt(brief)}
REDES DE LA CAMPAÑA: {", ".join(redes)}
IDIOMA DE RESPUESTA: {idioma}

No inventes datos de la marca (precios, cifras, clientes). Horarios en hora local del mercado.

Devuelve SOLO JSON con esta estructura:
{{
 "resumen": "2-3 frases con tu visión de la campaña",
 "mensaje_clave": "la idea principal que debe transmitir toda la campaña",
 "publico": [{{"segmento": "", "descripcion": "", "motivacion": ""}}],
 "mercados": [{{"mercado": "", "motivo": ""}}],
 "redes": [{{"red": "nombre exacto de una red de la lista", "prioridad": "alta|media|baja",
            "motivo": "", "horarios": ["Martes 19:00"], "frecuencia": "3 por semana"}}],
 "plan_7_dias": [{{"dia": "Lunes", "red": "", "idea": "", "formato": ""}}],
 "nota_para_el_equipo": "indicaciones breves para el copywriter y la creativa"
}}
Incluye en "redes" TODAS las redes de la campaña.
"""
    contents = [Image.open(io.BytesIO(b)) for b in (fotos_bytes or [])[:3]] + [prompt]
    return llamar_ia(client, modelos, contents, json_mode=True)


def escribir_publicaciones(client, modelos, brief, estrategia, redes, idioma, tono):
    """Marcos Vidal: textos por red, variante B y hashtags."""
    limites = ", ".join(f"{r} ({REDES[r]['limite']})" for r in redes)
    prompt = f"""
Eres {EQ['copy']['nombre']}, {EQ['copy']['rol']}. Escribe las publicaciones siguiendo la
estrategia de tu compañera Elena.

{_brief_txt(brief)}
ESTRATEGIA: {json.dumps(estrategia, ensure_ascii=False)}
TONO: {tono}
IDIOMA: {idioma}
REDES Y LÍMITE DE CARACTERES (incluyendo hashtags y enlace): {limites}

Reglas:
- Adapta el estilo a cada red (Bluesky y X muy breves, LinkedIn profesional, Instagram con
  emojis y gancho, YouTube con título y descripción, WhatsApp cercano).
- Escribe {{LINK}} donde deba ir el enlace, una sola vez por texto.
- La primera línea debe ser un gancho que haga parar el scroll.
- No inventes precios, cifras, opiniones ni testimonios.
- Entre 0 y 5 hashtags por red (ninguno en WhatsApp).

Devuelve SOLO JSON:
{{
 "gancho_imagen": "frase de máximo 7 palabras para poner sobre las imágenes",
 "publicaciones": {{
   "NombreExactoDeLaRed": {{"texto": "", "variante_b": "otra versión con un gancho distinto",
                           "hashtags": ["#ejemplo"]}}
 }}
}}
Incluye TODAS las redes de la lista.
"""
    return llamar_ia(client, modelos, prompt, json_mode=True)


def escribir_guion(client, modelos, brief, estrategia, idioma, tono):
    """Lucía Ortega: guion de vídeo vertical a partir de grabaciones de pantalla o fotos."""
    prompt = f"""
Eres {EQ['creativa']['nombre']}, {EQ['creativa']['rol']}. Escribe un guion de vídeo vertical de
unos 30 segundos (Reels, TikTok, YouTube Shorts) para esta campaña.
Se grabará con capturas o grabaciones de pantalla del producto y textos en pantalla.

{_brief_txt(brief)}
MENSAJE CLAVE: {estrategia.get('mensaje_clave', '')}
TONO: {tono}
IDIOMA: {idioma}

Estructura en Markdown:
### Gancho (0-3 s)
### Desarrollo
Tabla con columnas: Segundos | Qué se ve | Texto en pantalla | Voz en off
### Cierre y llamada a la acción
### Música
Estilo recomendado. Indica que debe ser música libre de derechos.
"""
    return llamar_ia(client, modelos, prompt)


def informe_resultados(client, modelos, brief, metricas, idioma):
    """Sara Méndez: informe a partir de las métricas que introduce el usuario."""
    prompt = f"""
Eres {EQ['analista']['nombre']}, {EQ['analista']['rol']}. Escribe un informe breve y claro
para el cliente a partir de estas métricas de la campaña.

{_brief_txt(brief)}
MÉTRICAS POR RED: {json.dumps(metricas, ensure_ascii=False)}
IDIOMA: {idioma}

Estructura en Markdown:
### Resumen en una frase
### Qué ha funcionado
### Qué no ha funcionado
### Próximos pasos (3 acciones concretas)
Basa todo en los datos. Si faltan datos para concluir algo, dilo.
"""
    return llamar_ia(client, modelos, prompt)


# -------------------------------------------------------------------
# TEXTOS Y ENLACES
# -------------------------------------------------------------------
def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "campana"


def enlace_utm(url, red, campana):
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={slug(red)}&utm_medium=social&utm_campaign={slug(campana)}"


def texto_final(pub, link, red):
    """Texto listo para publicar: enlace insertado, hashtags y límite de la red respetado."""
    base = (pub.get("texto") or "").strip()
    if link:
        base = base.replace("{LINK}", link) if "{LINK}" in base else f"{base}\n\n{link}"
    else:
        base = base.replace("{LINK}", "").strip()

    tags = [h if h.startswith("#") else f"#{h}" for h in (pub.get("hashtags") or []) if h]
    limite = REDES[red]["limite"]

    while tags and len(base) + 2 + len(" ".join(tags)) > limite:
        tags.pop()
    final = f"{base}\n\n{' '.join(tags)}" if tags else base

    if len(final) > limite:
        recorte = limite - 1
        if link and link in final and len(link) < limite - 10:
            cuerpo = final.replace(link, "").strip()
            final = cuerpo[: recorte - len(link) - 2].rstrip() + "…\n\n" + link
        else:
            final = final[:recorte].rstrip() + "…"
    return final


# -------------------------------------------------------------------
# PIEZAS VISUALES (Lucía)
# -------------------------------------------------------------------
def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(tamano):
    for nombre in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:
        return ImageFont.load_default()


def _ajustar(draw, texto, fuente, ancho_max, max_lineas=3):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas[:max_lineas]


def crear_pieza(foto_bytes, tamano, color, gancho, logo_bytes=None):
    """Recorta la foto al formato de la red y añade banda de marca con el gancho y el logo."""
    w, h = tamano
    rgb = _hex_rgb(color)
    claro = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) > 160
    color_texto = (20, 20, 20) if claro else (255, 255, 255)

    if foto_bytes:
        img = ImageOps.fit(Image.open(io.BytesIO(foto_bytes)).convert("RGB"), tamano,
                           Image.Resampling.LANCZOS)
        banda = int(h * 0.18)
        zona = (0, h - banda, w, h)
    else:
        img = Image.new("RGB", tamano, rgb)
        zona = (0, 0, w, h)

    draw = ImageDraw.Draw(img, "RGBA")
    if foto_bytes:
        draw.rectangle(zona, fill=(*rgb, 232))

    if gancho:
        alto_zona = zona[3] - zona[1]
        tam = int(min(alto_zona * (0.28 if foto_bytes else 0.09), w * 0.075))
        fuente = _fuente(max(tam, 18))
        lineas = _ajustar(draw, gancho, fuente, w * 0.88)
        alto_linea = int(fuente.size * 1.2) if hasattr(fuente, "size") else 20
        y = zona[1] + (alto_zona - alto_linea * len(lineas)) // 2
        for linea in lineas:
            ancho = draw.textlength(linea, font=fuente)
            draw.text(((w - ancho) / 2, y), linea, font=fuente, fill=color_texto)
            y += alto_linea

    if logo_bytes:
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        logo.thumbnail((int(w * 0.2), int(h * 0.1)))
        img.paste(logo, (int(w * 0.04), int(h * 0.04)), logo)

    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=88)
    return salida.getvalue()


def _comprimir(imagen, max_bytes=950_000):
    if len(imagen) <= max_bytes:
        return imagen
    img = Image.open(io.BytesIO(imagen)).convert("RGB")
    for calidad in (80, 70, 60, 50, 40):
        out = io.BytesIO()
        img.save(out, "JPEG", quality=calidad)
        if out.tell() <= max_bytes:
            return out.getvalue()
    img.thumbnail((1000, 1000))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=60)
    return out.getvalue()


# -------------------------------------------------------------------
# CONECTORES (Daniel)
# -------------------------------------------------------------------
def _telegram(texto, imagen, s):
    r = requests.post(
        f"https://api.telegram.org/bot{s['TELEGRAM_BOT_TOKEN']}/sendPhoto",
        data={"chat_id": s["TELEGRAM_CHAT_ID"], "caption": texto[:1024]},
        files={"photo": ("pieza.jpg", imagen, "image/jpeg")},
        timeout=60,
    )
    datos = r.json()
    if not datos.get("ok"):
        raise RuntimeError(datos.get("description", "Telegram rechazó la publicación."))
    chat = str(s["TELEGRAM_CHAT_ID"])
    msg_id = datos["result"]["message_id"]
    return f"https://t.me/{chat[1:]}/{msg_id}" if chat.startswith("@") else "Publicado en Telegram"


def _bluesky(texto, imagen, s):
    base = "https://bsky.social/xrpc/"
    sesion = requests.post(base + "com.atproto.server.createSession",
                           json={"identifier": s["BLUESKY_HANDLE"],
                                 "password": s["BLUESKY_APP_PASSWORD"]}, timeout=30)
    if sesion.status_code != 200:
        raise RuntimeError(f"Bluesky no aceptó el inicio de sesión: {sesion.text[:200]}")
    sesion = sesion.json()
    cab = {"Authorization": f"Bearer {sesion['accessJwt']}"}

    blob = requests.post(base + "com.atproto.repo.uploadBlob",
                         headers={**cab, "Content-Type": "image/jpeg"},
                         data=_comprimir(imagen), timeout=60)
    blob.raise_for_status()

    texto = texto if len(texto) <= 300 else texto[:299] + "…"
    registro = {
        "$type": "app.bsky.feed.post",
        "text": texto,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images",
                  "images": [{"alt": texto[:200], "image": blob.json()["blob"]}]},
    }
    facetas = []
    for m in re.finditer(r"https?://\S+", texto):
        inicio = len(texto[:m.start()].encode("utf-8"))
        facetas.append({"index": {"byteStart": inicio,
                                  "byteEnd": inicio + len(m.group().encode("utf-8"))},
                        "features": [{"$type": "app.bsky.richtext.facet#link",
                                      "uri": m.group()}]})
    if facetas:
        registro["facets"] = facetas

    r = requests.post(base + "com.atproto.repo.createRecord", headers=cab,
                      json={"repo": sesion["did"], "collection": "app.bsky.feed.post",
                            "record": registro}, timeout=30)
    r.raise_for_status()
    post_id = r.json()["uri"].split("/")[-1]
    return f"https://bsky.app/profile/{s['BLUESKY_HANDLE']}/post/{post_id}"


def _facebook(texto, imagen, s):
    version = s.get("FB_GRAPH_VERSION", "v23.0")
    r = requests.post(
        f"https://graph.facebook.com/{version}/{s['FB_PAGE_ID']}/photos",
        data={"message": texto, "access_token": s["FB_PAGE_TOKEN"]},
        files={"source": ("pieza.jpg", imagen, "image/jpeg")},
        timeout=60,
    )
    datos = r.json()
    if "error" in datos:
        raise RuntimeError(datos["error"].get("message", "Facebook rechazó la publicación."))
    return f"https://www.facebook.com/{datos.get('post_id', datos.get('id'))}"


def publicar(red, texto, imagen, secretos):
    if not conectado(red, secretos):
        raise RuntimeError(f"{red} no está conectado. Añade sus claves en los Secrets.")
    if red == "Telegram":
        return _telegram(texto, imagen, secretos)
    if red == "Bluesky":
        return _bluesky(texto, imagen, secretos)
    if red == "Facebook":
        return _facebook(texto, imagen, secretos)
    raise RuntimeError(f"{red} todavía no tiene publicación directa.")


# -------------------------------------------------------------------
# DESCARGAS
# -------------------------------------------------------------------
def pack_zip(redes, piezas, textos, guion, estrategia):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for red in redes:
            carpeta = re.sub(r"[^\w]+", "_", red).strip("_")
            z.writestr(f"{carpeta}/imagen.jpg", piezas[red])
            z.writestr(f"{carpeta}/texto.txt", textos[red])
        z.writestr("guion_video.md", guion or "")
        z.writestr("estrategia.json", json.dumps(estrategia, ensure_ascii=False, indent=2))
    return buffer.getvalue()
