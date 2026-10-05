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

import base64
import requests
import markdown as md
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
RETRATOS = {'estrategia': 'mujer española de unos 40 años, pelo castaño recogido, americana azul marino, sonrisa segura', 'copy': 'hombre español de unos 32 años, barba corta, jersey gris, gesto creativo y cercano', 'creativa': 'mujer española de unos 30 años, pelo ondulado oscuro, camisa negra, estilo creativo', 'community': 'hombre español de unos 27 años, pelo corto, camisa vaquera, sonrisa amable', 'analista': 'mujer española de unos 35 años, gafas finas, blusa blanca, expresión analítica y tranquila', 'talento': 'hombre español de unos 38 años, camiseta oscura y chaqueta informal, gesto sociable'}
for _m in EQUIPO:
    _m["retrato"] = RETRATOS[_m["id"]]
    _m["color"] = {'estrategia': '#C084FC', 'copy': '#22D3EE', 'creativa': '#F472B6', 'community': '#FBBF24', 'analista': '#34D399', 'talento': '#60A5FA'}[_m["id"]]
EQ = {m["id"]: m for m in EQUIPO}

ESTILO_RETRATO = (", retrato corporativo para la web de una agencia de marketing, fondo de oficina "
                  "moderna desenfocado con luces de neón moradas suaves, luz natural en la cara, "
                  "fotografía realista de alta calidad, encuadre de hombros hacia arriba, mirando a cámara")

MODELOS_IMAGEN = ["gemini-2.5-flash-image", "gemini-3-pro-image-preview", "imagen-4.0-generate-001"]

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

# tipo: auto = se puede conectar y publicar directo · manual = descarga para subir a mano
REDES = {
    "Telegram":       {"tamano": (1080, 1080), "limite": 1024, "tipo": "auto"},
    "Bluesky":        {"tamano": (1200, 675),  "limite": 300,  "tipo": "auto"},
    "Facebook":       {"tamano": (1080, 1350), "limite": 5000, "tipo": "auto"},
    "Instagram":      {"tamano": (1080, 1350), "limite": 2200, "tipo": "auto"},
    "Threads":        {"tamano": (1080, 1350), "limite": 500,  "tipo": "auto"},
    "LinkedIn":       {"tamano": (1200, 627),  "limite": 3000, "tipo": "auto"},
    "Pinterest":      {"tamano": (1000, 1500), "limite": 500,  "tipo": "auto"},
    "Discord":        {"tamano": (1200, 675),  "limite": 2000, "tipo": "auto"},
    "Mastodon":       {"tamano": (1200, 675),  "limite": 500,  "tipo": "auto"},
    "Blogger (Google)": {"tamano": (1200, 630), "limite": 60000, "tipo": "auto", "articulo": True},
    "WordPress":      {"tamano": (1200, 630),  "limite": 60000, "tipo": "auto", "articulo": True},
    "Dev.to":         {"tamano": (1000, 420),  "limite": 60000, "tipo": "auto", "articulo": True},
    "Newsletter (Brevo)": {"tamano": (1200, 630), "limite": 60000, "tipo": "auto", "articulo": True},
    "X (Twitter)":    {"tamano": (1600, 900),  "limite": 280,  "tipo": "manual",
                       "motivo": "Su API para publicar es de pago."},
    "TikTok":         {"tamano": (1080, 1920), "limite": 2200, "tipo": "manual",
                       "motivo": "Exige una auditoría de TikTok para publicar por API."},
    "YouTube Shorts": {"tamano": (1080, 1920), "limite": 5000, "tipo": "manual",
                       "motivo": "Publica vídeos y la agencia de momento entrega imagen y guion."},
    "WhatsApp":       {"tamano": (1080, 1080), "limite": 1000, "tipo": "manual",
                       "motivo": "Los canales de WhatsApp no tienen API."},
    "Reddit":         {"tamano": (1200, 675),  "limite": 3000, "tipo": "manual",
                       "motivo": "Sus comunidades castigan la autopromoción automática: mejor a mano y participando."},
    "Tumblr":         {"tamano": (1080, 1350), "limite": 2000, "tipo": "manual",
                       "motivo": "Su conexión es más compleja; se añadirá más adelante."},
    "Medium":         {"tamano": (1400, 788),  "limite": 60000, "tipo": "manual", "articulo": True,
                       "motivo": "Ya no da acceso nuevo a su API de publicación."},
    "Hashnode":       {"tamano": (1600, 840),  "limite": 60000, "tipo": "manual", "articulo": True,
                       "motivo": "Se añadirá más adelante."},
    "Perfil de Empresa de Google": {"tamano": (1200, 900), "limite": 1500, "tipo": "manual",
                       "motivo": "Su API requiere aprobación y suele exigir atención presencial."},
}

TIPOS = {
    "auto": "Se publica directamente desde la app",
    "manual": "Descarga imagen y texto para subirlo a mano",
}


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
- Entre 0 y 5 hashtags por red (ninguno en WhatsApp ni en artículos).
- En blogs y newsletter ({", ".join(r for r in redes if REDES[r].get("articulo")) or "ninguna"}) escribe
  un artículo de 300 a 500 palabras en Markdown, con subtítulos, que aporte valor real y no
  sea solo publicidad.
- Cada publicación lleva un "titulo" (en artículos, titular atractivo con palabras clave).

Devuelve SOLO JSON:
{{
 "gancho_imagen": "frase de máximo 7 palabras para poner sobre las imágenes",
 "publicaciones": {{
   "NombreExactoDeLaRed": {{"titulo": "", "texto": "", "variante_b": "otra versión con un gancho distinto",
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

    if REDES[red].get("articulo"):
        base = (pub.get("texto") or "").strip()
        if link:
            base = (base.replace("{LINK}", link) if "{LINK}" in base
                    else f"{base}\n\n[Más información]({link})")
        return base.replace("{LINK}", "").strip()

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
def _ok(r, nombre):
    if r.status_code >= 400:
        raise RuntimeError(f"{nombre} respondió {r.status_code}: {r.text[:300]}")
    return r


def _html(texto):
    return md.markdown(texto or "", extensions=["extra"])


def _primer_enlace(texto):
    m = re.search(r"https?://\S+", texto or "")
    return m.group().rstrip(").,") if m else ""


# --- Telegram ---
def _telegram_probar(c):
    r = requests.get(f"https://api.telegram.org/bot{c['TELEGRAM_BOT_TOKEN']}/getChat",
                     params={"chat_id": c["TELEGRAM_CHAT_ID"]}, timeout=20).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description", "Token o canal incorrectos."))
    return f"Canal: {r['result'].get('title', c['TELEGRAM_CHAT_ID'])}"


def _telegram(texto, titulo, imagen, c):
    datos = requests.post(
        f"https://api.telegram.org/bot{c['TELEGRAM_BOT_TOKEN']}/sendPhoto",
        data={"chat_id": c["TELEGRAM_CHAT_ID"], "caption": texto[:1024]},
        files={"photo": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60).json()
    if not datos.get("ok"):
        raise RuntimeError(datos.get("description", "Telegram rechazó la publicación."))
    chat = str(c["TELEGRAM_CHAT_ID"])
    msg_id = datos["result"]["message_id"]
    return f"https://t.me/{chat[1:]}/{msg_id}" if chat.startswith("@") else "Publicado en Telegram"


# --- Bluesky ---
def _bsky_sesion(c):
    r = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                      json={"identifier": c["BLUESKY_HANDLE"],
                            "password": c["BLUESKY_APP_PASSWORD"]}, timeout=30)
    return _ok(r, "Bluesky").json()


def _bluesky_probar(c):
    return f"Cuenta: @{_bsky_sesion(c)['handle']}"


def _bluesky(texto, titulo, imagen, c):
    base = "https://bsky.social/xrpc/"
    sesion = _bsky_sesion(c)
    cab = {"Authorization": f"Bearer {sesion['accessJwt']}"}
    blob = _ok(requests.post(base + "com.atproto.repo.uploadBlob",
                             headers={**cab, "Content-Type": "image/jpeg"},
                             data=_comprimir(imagen), timeout=60), "Bluesky")
    texto = texto if len(texto) <= 300 else texto[:299] + "…"
    registro = {
        "$type": "app.bsky.feed.post", "text": texto,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images",
                  "images": [{"alt": texto[:200], "image": blob.json()["blob"]}]},
    }
    facetas = []
    for m in re.finditer(r"https?://\S+", texto):
        inicio = len(texto[:m.start()].encode("utf-8"))
        facetas.append({"index": {"byteStart": inicio,
                                  "byteEnd": inicio + len(m.group().encode("utf-8"))},
                        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}]})
    if facetas:
        registro["facets"] = facetas
    r = _ok(requests.post(base + "com.atproto.repo.createRecord", headers=cab,
                          json={"repo": sesion["did"], "collection": "app.bsky.feed.post",
                                "record": registro}, timeout=30), "Bluesky")
    return f"https://bsky.app/profile/{sesion['handle']}/post/{r.json()['uri'].split('/')[-1]}"


# --- Meta: Facebook, Instagram, Threads ---
def _graph(c):
    return f"https://graph.facebook.com/{c.get('FB_GRAPH_VERSION') or 'v23.0'}"


def _facebook_probar(c):
    r = _ok(requests.get(f"{_graph(c)}/{c['FB_PAGE_ID']}",
                         params={"fields": "name", "access_token": c["FB_PAGE_TOKEN"]},
                         timeout=20), "Facebook").json()
    return f"Página: {r.get('name')}"


def _facebook(texto, titulo, imagen, c):
    datos = _ok(requests.post(f"{_graph(c)}/{c['FB_PAGE_ID']}/photos",
                              data={"message": texto, "access_token": c["FB_PAGE_TOKEN"]},
                              files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                              timeout=60), "Facebook").json()
    return f"https://www.facebook.com/{datos.get('post_id', datos.get('id'))}"


def _alojar_imagen(imagen, c):
    """Sube la imagen como foto oculta de tu página de Facebook y devuelve su URL pública.
    Instagram y Threads solo aceptan imágenes por URL."""
    foto = _ok(requests.post(f"{_graph(c)}/{c['FB_PAGE_ID']}/photos",
                             data={"published": "false", "access_token": c["FB_PAGE_TOKEN"]},
                             files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                             timeout=60), "Facebook").json()
    info = _ok(requests.get(f"{_graph(c)}/{foto['id']}",
                            params={"fields": "images", "access_token": c["FB_PAGE_TOKEN"]},
                            timeout=20), "Facebook").json()
    return info["images"][0]["source"]


def _instagram_probar(c):
    r = _ok(requests.get(f"{_graph(c)}/{c['IG_USER_ID']}",
                         params={"fields": "username", "access_token": c["FB_PAGE_TOKEN"]},
                         timeout=20), "Instagram").json()
    return f"Cuenta: @{r.get('username')}"


def _instagram(texto, titulo, imagen, c):
    g, tok, ig = _graph(c), c["FB_PAGE_TOKEN"], c["IG_USER_ID"]
    cont = _ok(requests.post(f"{g}/{ig}/media", data={"image_url": _alojar_imagen(imagen, c),
                                                       "caption": texto, "access_token": tok},
                             timeout=60), "Instagram").json()["id"]
    for _ in range(15):
        estado = requests.get(f"{g}/{cont}", params={"fields": "status_code",
                                                      "access_token": tok}, timeout=20).json()
        if estado.get("status_code") == "FINISHED":
            break
        if estado.get("status_code") == "ERROR":
            raise RuntimeError("Instagram no pudo procesar la imagen.")
        time.sleep(2)
    pub = _ok(requests.post(f"{g}/{ig}/media_publish",
                            data={"creation_id": cont, "access_token": tok}, timeout=60),
              "Instagram").json()
    enlace = requests.get(f"{g}/{pub['id']}", params={"fields": "permalink",
                                                       "access_token": tok}, timeout=20).json()
    return enlace.get("permalink", "Publicado en Instagram")


def _threads_probar(c):
    r = _ok(requests.get("https://graph.threads.net/v1.0/me",
                         params={"fields": "username", "access_token": c["THREADS_TOKEN"]},
                         timeout=20), "Threads").json()
    return f"Cuenta: @{r.get('username')}"


def _threads(texto, titulo, imagen, c):
    base, tok, uid = "https://graph.threads.net/v1.0", c["THREADS_TOKEN"], c["THREADS_USER_ID"]
    cont = _ok(requests.post(f"{base}/{uid}/threads",
                             data={"media_type": "IMAGE", "image_url": _alojar_imagen(imagen, c),
                                   "text": texto[:500], "access_token": tok}, timeout=60),
               "Threads").json()["id"]
    for _ in range(15):
        estado = requests.get(f"{base}/{cont}", params={"fields": "status",
                                                         "access_token": tok}, timeout=20).json()
        if estado.get("status") == "FINISHED":
            break
        if estado.get("status") == "ERROR":
            raise RuntimeError("Threads no pudo procesar la imagen.")
        time.sleep(2)
    _ok(requests.post(f"{base}/{uid}/threads_publish",
                      data={"creation_id": cont, "access_token": tok}, timeout=60), "Threads")
    return "Publicado en Threads"


# --- LinkedIn ---
def _li_cab(c):
    version = c.get("LINKEDIN_VERSION") or (dt.date.today().replace(day=1)
                                             - dt.timedelta(days=60)).strftime("%Y%m")
    return {"Authorization": f"Bearer {c['LINKEDIN_TOKEN']}", "LinkedIn-Version": version,
            "X-Restli-Protocol-Version": "2.0.0"}


def _li_autor(c):
    if c.get("LINKEDIN_URN"):
        return c["LINKEDIN_URN"], "página indicada"
    r = _ok(requests.get("https://api.linkedin.com/v2/userinfo",
                         headers={"Authorization": f"Bearer {c['LINKEDIN_TOKEN']}"}, timeout=20),
            "LinkedIn").json()
    return f"urn:li:person:{r['sub']}", r.get("name", "")


def _linkedin_probar(c):
    return f"Publicará como: {_li_autor(c)[1]}"


def _linkedin(texto, titulo, imagen, c):
    autor, _ = _li_autor(c)
    cab = _li_cab(c)
    ini = _ok(requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                            headers=cab, json={"initializeUploadRequest": {"owner": autor}},
                            timeout=30), "LinkedIn").json()["value"]
    _ok(requests.put(ini["uploadUrl"], data=imagen,
                     headers={"Authorization": cab["Authorization"]}, timeout=60), "LinkedIn")
    r = _ok(requests.post("https://api.linkedin.com/rest/posts", headers=cab, json={
        "author": autor, "commentary": texto, "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "content": {"media": {"id": ini["image"], "altText": titulo or texto[:100]}},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False,
    }, timeout=30), "LinkedIn")
    urn = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{urn}" if urn else "Publicado en LinkedIn"


# --- Pinterest ---
def _pinterest_probar(c):
    cab = {"Authorization": f"Bearer {c['PINTEREST_TOKEN']}"}
    yo = _ok(requests.get("https://api.pinterest.com/v5/user_account", headers=cab, timeout=20),
             "Pinterest").json()
    tableros = requests.get("https://api.pinterest.com/v5/boards", headers=cab,
                            timeout=20).json().get("items", [])
    lista = "; ".join(f"{t['name']} → {t['id']}" for t in tableros[:15])
    aviso = "" if c.get("PINTEREST_BOARD_ID") else " Copia el ID del tablero donde quieras publicar."
    return f"Cuenta: {yo.get('username')}. Tableros: {lista or 'ninguno'}.{aviso}"


def _pinterest(texto, titulo, imagen, c):
    if not c.get("PINTEREST_BOARD_ID"):
        raise RuntimeError("Falta el ID del tablero.")
    cuerpo = {"board_id": c["PINTEREST_BOARD_ID"], "title": (titulo or texto)[:100],
              "description": texto[:500],
              "media_source": {"source_type": "image_base64", "content_type": "image/jpeg",
                               "data": base64.b64encode(imagen).decode()}}
    enlace = _primer_enlace(texto)
    if enlace:
        cuerpo["link"] = enlace
    r = _ok(requests.post("https://api.pinterest.com/v5/pins", json=cuerpo, timeout=60,
                          headers={"Authorization": f"Bearer {c['PINTEREST_TOKEN']}"}),
            "Pinterest").json()
    return f"https://www.pinterest.com/pin/{r['id']}/"


# --- Discord ---
def _discord_probar(c):
    r = _ok(requests.get(c["DISCORD_WEBHOOK_URL"], timeout=20), "Discord").json()
    return f"Webhook: {r.get('name')}"


def _discord(texto, titulo, imagen, c):
    _ok(requests.post(c["DISCORD_WEBHOOK_URL"], params={"wait": "true"},
                      data={"payload_json": json.dumps({"content": texto[:2000]})},
                      files={"files[0]": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60),
        "Discord")
    return "Publicado en Discord"


# --- Mastodon ---
def _masto(c):
    return c["MASTODON_URL"].rstrip("/"), {"Authorization": f"Bearer {c['MASTODON_TOKEN']}"}


def _mastodon_probar(c):
    base, cab = _masto(c)
    r = _ok(requests.get(f"{base}/api/v1/accounts/verify_credentials", headers=cab, timeout=20),
            "Mastodon").json()
    return f"Cuenta: @{r.get('acct')}"


def _mastodon(texto, titulo, imagen, c):
    base, cab = _masto(c)
    media = _ok(requests.post(f"{base}/api/v2/media", headers=cab,
                              files={"file": ("pieza.jpg", imagen, "image/jpeg")},
                              data={"description": (titulo or texto)[:200]}, timeout=60),
                "Mastodon").json()
    for _ in range(10):
        if media.get("url"):
            break
        time.sleep(2)
        media = requests.get(f"{base}/api/v1/media/{media['id']}", headers=cab, timeout=20).json()
    r = _ok(requests.post(f"{base}/api/v1/statuses", headers=cab,
                          data={"status": texto[:500], "media_ids[]": media["id"]}, timeout=30),
            "Mastodon").json()
    return r.get("url", "Publicado en Mastodon")


# --- Blogger (Google) ---
def _google_token(c):
    r = _ok(requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": c["BLOGGER_CLIENT_ID"], "client_secret": c["BLOGGER_CLIENT_SECRET"],
        "refresh_token": c["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"},
        timeout=20), "Google").json()
    return r["access_token"]


def _blogger_probar(c):
    r = _ok(requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{c['BLOGGER_BLOG_ID']}",
                         headers={"Authorization": f"Bearer {_google_token(c)}"}, timeout=20),
            "Blogger").json()
    return f"Blog: {r.get('name')}"


def _blogger(texto, titulo, imagen, c):
    r = _ok(requests.post(
        f"https://www.googleapis.com/blogger/v3/blogs/{c['BLOGGER_BLOG_ID']}/posts/",
        headers={"Authorization": f"Bearer {_google_token(c)}"},
        json={"title": titulo or "Novedades", "content": _html(texto)}, timeout=30),
        "Blogger").json()
    return r.get("url", "Publicado en Blogger")


# --- WordPress ---
def _wp(c):
    return c["WP_URL"].rstrip("/") + "/wp-json/wp/v2", (c["WP_USER"], c["WP_APP_PASSWORD"])


def _wordpress_probar(c):
    base, auth = _wp(c)
    r = _ok(requests.get(f"{base}/users/me", auth=auth, timeout=20), "WordPress").json()
    return f"Usuario: {r.get('name')}"


def _wordpress(texto, titulo, imagen, c):
    base, auth = _wp(c)
    media = _ok(requests.post(f"{base}/media", auth=auth, data=imagen, timeout=60, headers={
        "Content-Disposition": 'attachment; filename="pieza.jpg"', "Content-Type": "image/jpeg"}),
        "WordPress").json()
    r = _ok(requests.post(f"{base}/posts", auth=auth, timeout=30, json={
        "title": titulo or "Novedades", "content": _html(texto), "status": "publish",
        "featured_media": media["id"]}), "WordPress").json()
    return r.get("link", "Publicado en WordPress")


# --- Dev.to ---
def _devto_probar(c):
    r = _ok(requests.get("https://dev.to/api/users/me", headers={"api-key": c["DEVTO_API_KEY"]},
                         timeout=20), "Dev.to").json()
    return f"Cuenta: @{r.get('username')}"


def _devto(texto, titulo, imagen, c, etiquetas=()):
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in etiquetas][:4]
    r = _ok(requests.post("https://dev.to/api/articles", headers={"api-key": c["DEVTO_API_KEY"]},
                          json={"article": {"title": titulo or "Novedades", "body_markdown": texto,
                                            "published": True, "tags": [t for t in tags if t]}},
                          timeout=30), "Dev.to").json()
    return r.get("url", "Publicado en Dev.to")


# --- Newsletter Brevo ---
def _brevo_probar(c):
    r = _ok(requests.get("https://api.brevo.com/v3/account", headers={"api-key": c["BREVO_API_KEY"]},
                         timeout=20), "Brevo").json()
    return f"Cuenta: {r.get('email')}"


def _brevo(texto, titulo, imagen, c):
    cab = {"api-key": c["BREVO_API_KEY"]}
    camp = _ok(requests.post("https://api.brevo.com/v3/emailCampaigns", headers=cab, json={
        "name": f"PublishFlow {dt.datetime.now():%Y-%m-%d %H:%M}",
        "subject": titulo or "Novedades",
        "sender": {"name": c["BREVO_SENDER_NAME"], "email": c["BREVO_SENDER_EMAIL"]},
        "type": "classic", "htmlContent": _html(texto),
        "recipients": {"listIds": [int(c["BREVO_LIST_ID"])]}}, timeout=30), "Brevo").json()
    _ok(requests.post(f"https://api.brevo.com/v3/emailCampaigns/{camp['id']}/sendNow",
                      headers=cab, timeout=30), "Brevo")
    return "Newsletter enviada"


def _campo(clave, etiqueta, secreto=False, ayuda=None, opcional=False):
    return {"clave": clave, "etiqueta": etiqueta, "secreto": secreto, "ayuda": ayuda,
            "opcional": opcional}


CONECTORES = {
    "Telegram": {
        "campos": [_campo("TELEGRAM_BOT_TOKEN", "Token del bot", True),
                   _campo("TELEGRAM_CHAT_ID", "Canal", ayuda="Ej.: @tucanal")],
        "pasos": "1. En Telegram, abre **@BotFather**, escribe `/newbot` y copia el token.\n"
                 "2. Añade el bot como **administrador** de tu canal.\n"
                 "3. Si el canal es público, su ID es su @nombre (ej. `@adeskcharts`).",
        "probar": _telegram_probar, "publicar": _telegram},
    "Bluesky": {
        "campos": [_campo("BLUESKY_HANDLE", "Usuario", ayuda="Ej.: tunombre.bsky.social"),
                   _campo("BLUESKY_APP_PASSWORD", "Contraseña de app", True)],
        "pasos": "1. En Bluesky: **Ajustes → Privacidad y seguridad → Contraseñas de app**.\n"
                 "2. Crea una nueva y cópiala. No uses tu contraseña normal.",
        "probar": _bluesky_probar, "publicar": _bluesky},
    "Facebook": {
        "campos": [_campo("FB_PAGE_ID", "ID de la página"),
                   _campo("FB_PAGE_TOKEN", "Token de la página", True),
                   _campo("FB_GRAPH_VERSION", "Versión de la API", ayuda="Ej.: v23.0", opcional=True)],
        "pasos": "1. Crea una app en **developers.facebook.com** (tipo empresa).\n"
                 "2. En el **Explorador de la API Graph**, pide los permisos `pages_manage_posts`, "
                 "`pages_read_engagement` e `instagram_content_publish`.\n"
                 "3. Genera un **token de página de larga duración** y cópialo.\n"
                 "4. El ID de la página está en **Información** de tu página.",
        "probar": _facebook_probar, "publicar": _facebook},
    "Instagram": {
        "campos": [_campo("IG_USER_ID", "ID de la cuenta de Instagram",
                          ayuda="Usa el mismo token que Facebook")],
        "requiere": ["Facebook"],
        "pasos": "1. Tu Instagram debe ser **cuenta profesional** y estar vinculada a tu página de Facebook.\n"
                 "2. Conecta primero **Facebook** (se usa su token y aloja las imágenes).\n"
                 "3. En el Explorador de la API Graph consulta "
                 "`TU_ID_DE_PAGINA?fields=instagram_business_account` y copia el ID que aparece.",
        "probar": _instagram_probar, "publicar": _instagram},
    "Threads": {
        "campos": [_campo("THREADS_USER_ID", "ID de usuario de Threads"),
                   _campo("THREADS_TOKEN", "Token de Threads", True)],
        "requiere": ["Facebook"],
        "pasos": "1. En tu app de Meta añade el caso de uso **Threads API** con permisos "
                 "`threads_basic` y `threads_content_publish`.\n"
                 "2. Genera un token de usuario de Threads.\n"
                 "3. Tu ID: pulsa *Probar* con el token y consulta `graph.threads.net/v1.0/me`.\n"
                 "4. Necesita **Facebook** conectado para alojar las imágenes.",
        "probar": _threads_probar, "publicar": _threads},
    "LinkedIn": {
        "campos": [_campo("LINKEDIN_TOKEN", "Token de acceso", True),
                   _campo("LINKEDIN_URN", "URN de página de empresa", opcional=True,
                          ayuda="Déjalo vacío para publicar en tu perfil"),
                   _campo("LINKEDIN_VERSION", "Versión de la API", opcional=True, ayuda="Ej.: 202508")],
        "pasos": "1. Crea una app en **linkedin.com/developers** y añade los productos "
                 "**Share on LinkedIn** y **Sign In with LinkedIn using OpenID Connect**.\n"
                 "2. En **Token Generator** crea un token con `openid`, `profile` y `w_member_social`.\n"
                 "3. El token caduca a los 60 días: renuévalo aquí cuando deje de funcionar.\n"
                 "4. Para páginas de empresa LinkedIn exige una aprobación aparte.",
        "probar": _linkedin_probar, "publicar": _linkedin},
    "Pinterest": {
        "campos": [_campo("PINTEREST_TOKEN", "Token de acceso", True),
                   _campo("PINTEREST_BOARD_ID", "ID del tablero", opcional=True,
                          ayuda="Pulsa Probar sin rellenarlo y te mostraré tus tableros")],
        "pasos": "1. Crea una app en **developers.pinterest.com** (requiere solicitar acceso).\n"
                 "2. Genera un token con los permisos `boards:read`, `pins:read` y `pins:write`.\n"
                 "3. Pulsa *Probar*: te mostraré tus tableros con su ID.",
        "probar": _pinterest_probar, "publicar": _pinterest},
    "Discord": {
        "campos": [_campo("DISCORD_WEBHOOK_URL", "URL del webhook", True)],
        "pasos": "1. En tu servidor: **Editar canal → Integraciones → Webhooks → Nuevo webhook**.\n"
                 "2. Pulsa **Copiar URL del webhook** y pégala aquí.",
        "probar": _discord_probar, "publicar": _discord},
    "Mastodon": {
        "campos": [_campo("MASTODON_URL", "Servidor", ayuda="Ej.: https://mastodon.social"),
                   _campo("MASTODON_TOKEN", "Token de acceso", True)],
        "pasos": "1. En Mastodon: **Preferencias → Desarrollo → Nueva aplicación**.\n"
                 "2. Marca los permisos `read:accounts`, `write:statuses` y `write:media`.\n"
                 "3. Guarda y copia **Tu token de acceso**.",
        "probar": _mastodon_probar, "publicar": _mastodon},
    "Blogger (Google)": {
        "campos": [_campo("BLOGGER_BLOG_ID", "ID del blog"),
                   _campo("BLOGGER_CLIENT_ID", "Client ID de Google"),
                   _campo("BLOGGER_CLIENT_SECRET", "Client secret de Google", True),
                   _campo("BLOGGER_REFRESH_TOKEN", "Refresh token", True)],
        "pasos": "1. En **console.cloud.google.com** activa **Blogger API v3**.\n"
                 "2. Crea credenciales **OAuth (aplicación web)** con la URI de redirección "
                 "`https://developers.google.com/oauthplayground`.\n"
                 "3. En la pantalla de consentimiento pon la app **en producción** "
                 "(si se queda en prueba, el acceso caduca a los 7 días).\n"
                 "4. Abre **developers.google.com/oauthplayground**, en el engranaje marca "
                 "*Use your own OAuth credentials*, autoriza `https://www.googleapis.com/auth/blogger` "
                 "y pulsa *Exchange authorization code for tokens*. Copia el **refresh token**.\n"
                 "5. El ID del blog es el número que aparece en la dirección del panel de Blogger.",
        "probar": _blogger_probar, "publicar": _blogger},
    "WordPress": {
        "campos": [_campo("WP_URL", "Dirección de tu web", ayuda="Ej.: https://adeskcharts.com"),
                   _campo("WP_USER", "Usuario"),
                   _campo("WP_APP_PASSWORD", "Contraseña de aplicación", True)],
        "pasos": "1. En tu WordPress: **Usuarios → Perfil → Contraseñas de aplicación**.\n"
                 "2. Escribe un nombre (PublishFlow), pulsa *Añadir* y copia la contraseña.",
        "probar": _wordpress_probar, "publicar": _wordpress},
    "Dev.to": {
        "campos": [_campo("DEVTO_API_KEY", "Clave de API", True)],
        "pasos": "1. En dev.to: **Settings → Extensions → DEV Community API Keys**.\n"
                 "2. Genera una clave y cópiala.",
        "probar": _devto_probar, "publicar": _devto},
    "Newsletter (Brevo)": {
        "campos": [_campo("BREVO_API_KEY", "Clave de API", True),
                   _campo("BREVO_SENDER_NAME", "Nombre del remitente"),
                   _campo("BREVO_SENDER_EMAIL", "Email del remitente (verificado en Brevo)"),
                   _campo("BREVO_LIST_ID", "ID de la lista de contactos")],
        "pasos": "1. En Brevo: **Ajustes → SMTP y API → Claves API → Generar**.\n"
                 "2. Verifica tu email de remitente en **Remitentes y dominios**.\n"
                 "3. El ID de la lista está en **Contactos → Listas**.\n"
                 "Envía solo a contactos que hayan aceptado recibir tus emails.",
        "probar": _brevo_probar, "publicar": _brevo},
}


def campos_obligatorios(red):
    return [c["clave"] for c in CONECTORES.get(red, {}).get("campos", []) if not c["opcional"]]


def conectado(red, cred):
    spec = CONECTORES.get(red)
    if not spec:
        return False
    if not all(cred.get(k) for k in campos_obligatorios(red)):
        return False
    return all(conectado(dep, cred) for dep in spec.get("requiere", []))


def probar(red, cred):
    spec = CONECTORES[red]
    faltan = [c["etiqueta"] for c in spec["campos"] if not c["opcional"] and not cred.get(c["clave"])]
    if faltan:
        raise RuntimeError("Faltan datos: " + ", ".join(faltan))
    for dep in spec.get("requiere", []):
        if not conectado(dep, cred):
            raise RuntimeError(f"Conecta primero {dep}.")
    return spec["probar"](cred)


def publicar(red, texto, titulo, imagen, cred, etiquetas=()):
    if not conectado(red, cred):
        raise RuntimeError(f"{red} no está conectado. Ve a la pestaña Conexiones.")
    if red == "Dev.to":
        return _devto(texto, titulo, imagen, cred, etiquetas)
    return CONECTORES[red]["publicar"](texto, titulo, imagen, cred)


def claves_de(red):
    return [c["clave"] for c in CONECTORES.get(red, {}).get("campos", [])]


def secrets_toml(cred):
    claves = [c["clave"] for spec in CONECTORES.values() for c in spec["campos"]]
    return "\n".join(f"{k} = {json.dumps(str(cred[k]))}" for k in claves if cred.get(k))


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


# -------------------------------------------------------------------
# FOTOS DEL EQUIPO
# -------------------------------------------------------------------
def recortar_retrato(datos, lado=512):
    img = ImageOps.fit(Image.open(io.BytesIO(datos)).convert("RGB"), (lado, lado),
                       Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def generar_retrato(client, miembro, modelos=None):
    """Retrato realista de una persona que no existe, con el modelo de imagen disponible."""
    prompt = "Fotografía de " + miembro["retrato"] + ESTILO_RETRATO
    ultimo = None
    for modelo in modelos or MODELOS_IMAGEN:
        try:
            if modelo.startswith("imagen"):
                r = client.models.generate_images(
                    model=modelo, prompt=prompt,
                    config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"))
                datos = r.generated_images[0].image.image_bytes
            else:
                r = client.models.generate_content(
                    model=modelo, contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
                datos = next((p.inline_data.data for p in r.candidates[0].content.parts
                              if getattr(p, "inline_data", None) and p.inline_data.data), None)
            if datos:
                return recortar_retrato(datos)
        except Exception as e:
            ultimo = e
    raise ultimo or RuntimeError("Ningún modelo de imagen devolvió una foto.")


def zip_fotos(fotos):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for id_miembro, datos in fotos.items():
            z.writestr(f"fotos/{id_miembro}.jpg", datos)
    return buffer.getvalue()
