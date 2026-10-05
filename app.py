import base64
import datetime as dt
import io
import json
import os
import re
import time
import urllib.parse
import zipfile

import pandas as pd
import requests
import streamlit as st
from google import genai
from groq import Groq
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# CONFIGURACIÓN STREAMLIT
# ---------------------------------------------------------
st.set_page_config(
    page_title="PublishFlow Agencia",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# CONSTANTES Y CONFIGURACIÓN DEL EQUIPO
# ---------------------------------------------------------
EQUIPO = [
    {"id": "estrategia", "nombre": "Elena Navarro Ruiz", "rol": "Directora de Estrategia", "color": "#C084FC", "bio": "Analiza producto, mercado y plan de contenidos."},
    {"id": "copy", "nombre": "Marcos Vidal Herrera", "rol": "Copywriter Senior", "color": "#22D3EE", "bio": "Textos por red, variantes B y hashtags."},
    {"id": "creativa", "nombre": "Lucia Ortega Blanco", "rol": "Directora Creativa", "color": "#F472B6", "bio": "Diseño gráfico y guion de vídeo vertical."},
    {"id": "community", "nombre": "Daniel Soto Morales", "rol": "Community Manager", "color": "#FBBF24", "bio": "Publicación directa y gestión de descargas."},
    {"id": "analista", "nombre": "Sara Mendez Castillo", "rol": "Analista de Resultados", "color": "#34D399", "bio": "Enlaces UTM y análisis de rendimiento."},
    {"id": "talento", "nombre": "Javier Romero Gil", "rol": "Ojeador de Talento", "color": "#60A5FA", "bio": "Prospección de creadores y afiliados."}
]

EQ = {m["id"]: m for m in EQUIPO}

MARCAS = {
    "AdeskCharts": {
        "descripcion": "Plataforma de análisis técnico y trading algorítmico con IA.",
        "url": "https://adeskcharts.com",
        "color": "#10B981"
    },
    "SoundSnip Studio PRO": {
        "descripcion": "Herramientas de audio avanzadas para DJs y productores musicales.",
        "url": "https://soundsnip.studio",
        "color": "#8B5CF6"
    }
}

REDES = {
    "Telegram": {"tipo": "auto", "tamano": (1200, 800), "limite": 1024, "articulo": False},
    "Bluesky": {"tipo": "auto", "tamano": (1200, 675), "limite": 300, "articulo": False},
    "Discord": {"tipo": "auto", "tamano": (1200, 675), "limite": 2000, "articulo": False},
    "Facebook": {"tipo": "auto", "tamano": (1200, 630), "limite": 2000, "articulo": False},
    "Instagram": {"tipo": "auto", "tamano": (1080, 1080), "limite": 2200, "articulo": False},
    "Threads": {"tipo": "auto", "tamano": (1080, 1080), "limite": 500, "articulo": False},
    "LinkedIn": {"tipo": "auto", "tamano": (1200, 627), "limite": 3000, "articulo": False},
    "Pinterest": {"tipo": "auto", "tamano": (1000, 1500), "limite": 500, "articulo": False},
    "Mastodon": {"tipo": "auto", "tamano": (1200, 675), "limite": 500, "articulo": False},
    "WordPress": {"tipo": "auto", "tamano": (1200, 630), "limite": 10000, "articulo": True},
    "Dev.to": {"tipo": "auto", "tamano": (1000, 420), "limite": 10000, "articulo": True},
    "Blogger": {"tipo": "auto", "tamano": (1200, 630), "limite": 10000, "articulo": True},
    "Brevo (Newsletter)": {"tipo": "auto", "tamano": (600, 400), "limite": 10000, "articulo": True},
    "X (Twitter)": {"tipo": "manual", "tamano": (1200, 675), "limite": 280, "motivo": "API de pago."},
    "TikTok": {"tipo": "manual", "tamano": (1080, 1920), "limite": 2200, "motivo": "Requiere verificación."},
    "YouTube Shorts": {"tipo": "manual", "tamano": (1080, 1920), "limite": 1000, "motivo": "Requiere render MP4."},
    "WhatsApp": {"tipo": "manual", "tamano": (1080, 1080), "limite": 1000, "motivo": "Canales cerrados."},
    "Reddit": {"tipo": "manual", "tamano": (1200, 630), "limite": 3000, "motivo": "Filtros antispam."},
    "Medium": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "API deshabilitada."},
    "Tumblr": {"tipo": "manual", "tamano": (1280, 1920), "limite": 4000, "motivo": "OAuth 1.0a."},
    "Hashnode": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "GraphQL."},
    "Google Business": {"tipo": "manual", "tamano": (720, 540), "limite": 1500, "motivo": "Verificación física."}
}

CONECTORES = {
    "Telegram": {
        "campos": [
            {"clave": "TELEGRAM_BOT_TOKEN", "etiqueta": "Bot Token", "secreto": True, "opcional": False, "ayuda": "Token de @BotFather"},
            {"clave": "TELEGRAM_CHAT_ID", "etiqueta": "Chat ID", "secreto": False, "opcional": False, "ayuda": "ID o @canal"}
        ]
    },
    "Bluesky": {
        "campos": [
            {"clave": "BLUESKY_HANDLE", "etiqueta": "Handle", "secreto": False, "opcional": False, "ayuda": "ej: tu.bsky.social"},
            {"clave": "BLUESKY_APP_PASSWORD", "etiqueta": "App Password", "secreto": True, "opcional": False, "ayuda": "Contraseña de app"}
        ]
    },
    "Discord": {
        "campos": [
            {"clave": "DISCORD_WEBHOOK_URL", "etiqueta": "Webhook URL", "secreto": True, "opcional": False, "ayuda": "URL Webhook"}
        ]
    },
    "Dev.to": {
        "campos": [
            {"clave": "DEVTO_API_KEY", "etiqueta": "API Key", "secreto": True, "opcional": False, "ayuda": "Settings > Extensions"}
        ]
    }
}

# ---------------------------------------------------------
# SISTEMA DE IA MULTI-NIVEL (GEMINI FREE -> GROQ -> GEMINI PAID)
# ---------------------------------------------------------
def ejecutar_ia(credenciales, prompt, response_schema=None):
    errores = []

    # Nivel 1: Gemini Free
    k1 = credenciales.get("GEMINI_FREE_KEY") or credenciales.get("GEMINI_API_KEY") or os.getenv("GEMINI_FREE_KEY")
    if k1:
        try:
            client = genai.Client(api_key=k1)
            cfg = {"response_mime_type": "application/json", "response_schema": response_schema} if response_schema else None
            for m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    res = client.models.generate_content(model=m, contents=prompt, config=cfg)
                    if res.text:
                        return res.text, f"🟢 Nivel 1 [Gemini {m}]"
                except Exception as e:
                    if "429" in str(e).lower():
                        break
                    continue
        except Exception as e:
            errores.append(f"Gemini Free: {e}")

    # Nivel 2: Groq
    k2 = credenciales.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if k2:
        try:
            client = Groq(api_key=k2)
            p_final = prompt
            if response_schema:
                p_final = f"{prompt}\n\nResponde ÚNICAMENTE en JSON válido con este formato:\n{json.dumps(response_schema)}"
            fmt = {"type": "json_object"} if response_schema else None
            for m in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    res = client.chat.completions.create(
                        messages=[{"role": "user", "content": p_final}],
                        model=m,
                        response_format=fmt
                    )
                    txt = res.choices[0].message.content
                    if txt:
                        return txt, f"🟡 Nivel 2 [Groq {m}]"
                except Exception as e:
                    if "429" in str(e).lower():
                        continue
                    break
        except Exception as e:
            errores.append(f"Groq: {e}")

    # Nivel 3: Gemini Paid
    k3 = credenciales.get("GEMINI_PAID_KEY") or os.getenv("GEMINI_PAID_KEY")
    if k3:
        try:
            client = genai.Client(api_key=k3)
            cfg = {"response_mime_type": "application/json", "response_schema": response_schema} if response_schema else None
            res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
            if res.text:
                return res.text, "🔴 Nivel 3 [Gemini Paid]"
        except Exception as e:
            errores.append(f"Gemini Paid: {e}")

    raise RuntimeError("No se pudo obtener respuesta de ninguna IA:\n" + "\n".join(errores))

# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------
def conectado(red, cred):
    if red not in CONECTORES:
        return False
    for c in CONECTORES[red]["campos"]:
        if not c.get("opcional") and not cred.get(c["clave"]):
            return False
    return True

def slug(txt):
    s = re.sub(r"[^\w\s-]", "", txt).strip().lower()
    return re.sub(r"[-\s]+", "_", s)

def enlace_utm(url, red, campana):
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(p.query)
    qs["utm_source"] = [slug(red)]
    qs["utm_medium"] = ["social"]
    qs["utm_campaign"] = [slug(campana)]
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(qs, doseq=True)))

def crear_pieza(foto_bytes, tamano, color_hex, gancho):
    w, h = tamano
    img = Image.new("RGB", (w, h), color="#120824")
    if foto_bytes:
        try:
            foto = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
            fw, fh = foto.size
            ratio = max(w / fw, h / fh)
            foto = foto.resize((int(fw * ratio), int(fh * ratio)), Image.Resampling.LANCZOS)
            cx, cy = (foto.size[0] - w) // 2, (foto.size[1] - h) // 2
            img.paste(foto.crop((cx, cy, cx + w, cy + h)), (0, 0))
        except Exception:
            pass

    overlay = Image.new("RGBA", (w, h), (15, 8, 30, 120))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    if gancho:
        texto = gancho.upper()
        font_size = max(24, int(min(w, h) * 0.055))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), texto, font=font)
        tx = (w - (bbox[2] - bbox[0])) // 2
        ty = h - int(h * 0.15)
        draw.text((tx + 2, ty + 2), texto, font=font, fill=(0, 0, 0, 240))
        draw.text((tx, ty), texto, font=font, fill=(255, 255, 255, 255))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=90)
    return out.getvalue()

# ---------------------------------------------------------
# INTERFAZ STREAMLIT
# ---------------------------------------------------------
CRED = {
    "GEMINI_FREE_KEY": st.secrets.get("GEMINI_FREE_KEY", st.secrets.get("GEMINI_API_KEY", "")),
    "GROQ_API_KEY": st.secrets.get("GROQ_API_KEY", ""),
    "GEMINI_PAID_KEY": st.secrets.get("GEMINI_PAID_KEY", ""),
    "TELEGRAM_BOT_TOKEN": st.secrets.get("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID": st.secrets.get("TELEGRAM_CHAT_ID", ""),
    "BLUESKY_HANDLE": st.secrets.get("BLUESKY_HANDLE", ""),
    "BLUESKY_APP_PASSWORD": st.secrets.get("BLUESKY_APP_PASSWORD", ""),
    "DISCORD_WEBHOOK_URL": st.secrets.get("DISCORD_WEBHOOK_URL", ""),
    "DEVTO_API_KEY": st.secrets.get("DEVTO_API_KEY", "")
}

if "campanas" not in st.session_state:
    st.session_state.campanas = []

# Sidebar
with st.sidebar:
    st.title("📣 PublishFlow")
    st.caption("Agencia de Marketing Autónomo")
    st.divider()

    st.subheader("Estado de Inteligencias")
    st.write(f"Nivel 1 (Gemini): {'🟢 Listo' if CRED['GEMINI_FREE_KEY'] else '⚪ Desactivado'}")
    st.write(f"Nivel 2 (Groq): {'🟡 Listo' if CRED['GROQ_API_KEY'] else '⚪ Desactivado'}")
    st.write(f"Nivel 3 (Paid): {'🔴 Listo' if CRED['GEMINI_PAID_KEY'] else '⚪ Desactivado'}")

    st.divider()
    conectadas = [r for r in CONECTORES if conectado(r, CRED)]
    st.subheader("Redes")
    st.write(f"🟢 {len(conectadas)} de {len(CONECTORES)} conectadas")

# Pestañas principales
tab_nuevo, tab_historial, tab_equipo, tab_buscador = st.tabs([
    "📋 Nuevo Encargo",
    "📁 Campañas Guardadas",
    "👥 Equipo",
    "🔍 Buscador de Talentos"
])

# Tab: Nuevo Encargo
with tab_nuevo:
    st.subheader("Configuración de Campaña")
    c1, c2 = st.columns(2)
    with c1:
        marca_sel = st.selectbox("Marca", list(MARCAS.keys()))
        marca_info = MARCAS[marca_sel]
        objetivo = st.selectbox("Objetivo principal", [
            "Conseguir registros en la plataforma",
            "Ventas directas y suscripciones",
            "Generar autoridad y comunidad",
            "Lanzamiento de nueva funcionalidad"
        ])
        oferta = st.text_input("Oferta / Gancho (CTA)", value="Prueba gratuita de 14 días sin tarjeta")
    with c2:
        mercado = st.selectbox("Mercado objetivo", ["España", "Latinoamérica", "Global (Hispano)", "Internacional (Inglés)"])
        idioma = st.selectbox("Idioma de redacción", ["Español", "Inglés"])
        tono = st.selectbox("Tono del equipo", ["Profesional y persuasivo", "Enérgico y directo", "Técnico y analítico"])
        redes_sel = st.multiselect("Canales de difusión", list(REDES.keys()), default=["Telegram", "Bluesky", "LinkedIn"])

    foto_subida = st.file_uploader("Imagen base para la creatividad (opcional)", type=["png", "jpg", "jpeg"])
    foto_bytes = foto_subida.read() if foto_subida else None

    if st.button("🚀 Lanzar campaña con el equipo", type="primary"):
        if not redes_sel:
            st.error("Selecciona al menos una red social.")
        elif not any([CRED["GEMINI_FREE_KEY"], CRED["GROQ_API_KEY"], CRED["GEMINI_PAID_KEY"]]):
            st.error("Configura al menos una clave en los Secrets.")
        else:
            brief = {
                "marca": marca_sel,
                "descripcion": marca_info["descripcion"],
                "url": marca_info["url"],
                "objetivo": objetivo,
                "mercado": mercado,
                "oferta": oferta
            }

            with st.spinner("Elena, Marcos y Lucía están elaborando la campaña..."):
                try:
                    # 1. Estrategia
                    p_est = f"Elena (Estrategia). Plan en {idioma} para {brief['marca']}: {brief['descripcion']}. Objetivo: {objetivo}. Redes: {', '.join(redes_sel)}"
                    schema_est = {
                        "type": "OBJECT",
                        "properties": {
                            "resumen": {"type": "STRING"},
                            "mensaje_clave": {"type": "STRING"},
                            "plan_7_dias": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "dia": {"type": "STRING"},
                                        "accion": {"type": "STRING"},
                                        "canal": {"type": "STRING"}
                                    },
                                    "required": ["dia", "accion", "canal"]
                                }
                            }
                        },
                        "required": ["resumen", "mensaje_clave", "plan_7_dias"]
                    }
                    raw_est, motor_usado = ejecutar_ia(CRED, p_est, schema_est)
                    est_datos = json.loads(raw_est)

                    # 2. Copys
                    p_copy = f"Marcos (Copywriter). Redacta copys en {idioma} ({tono}) para {brief['marca']}. Mensaje: {est_datos['mensaje_clave']}. Redes: {', '.join(redes_sel)}. Gancho para banner corto."
                    schema_copy = {
                        "type": "OBJECT",
                        "properties": {
                            "gancho_banner": {"type": "STRING"},
                            "copys": {
                                "type": "OBJECT",
                                "properties": {
                                    r: {
                                        "type": "OBJECT",
                                        "properties": {
                                            "texto": {"type": "STRING"},
                                            "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}}
                                        },
                                        "required": ["texto", "hashtags"]
                                    } for r in redes_sel
                                },
                                "required": list(redes_sel)
                            }
                        },
                        "required": ["gancho_banner", "copys"]
                    }
                    raw_copy, _ = ejecutar_ia(CRED, p_copy, schema_copy)
                    copy_datos = json.loads(raw_copy)

                    # 3. Piezas gráficas
                    piezas = {}
                    gancho_b = copy_datos.get("gancho_banner", brief["marca"])
                    for r in redes_sel:
                        piezas[r] = crear_pieza(foto_bytes, REDES[r]["tamano"], marca_info["color"], gancho_b)

                    # Guardar en sesión
                    campana = {
                        "id": f"CAMP-{int(time.time())}",
                        "fecha": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "marca": marca_sel,
                        "motor": motor_usado,
                        "estrategia": est_datos,
                        "copys": copy_datos,
                        "piezas": piezas,
                        "redes": redes_sel
                    }
                    st.session_state.campanas.insert(0, campana)
                    st.success(f"¡Campaña generada con éxito! Resuelto con: {motor_usado}")

                except Exception as e:
                    st.error(f"Error procesando el encargo: {e}")

# Tab: Campañas Guardadas
with tab_historial:
    st.subheader("Campañas Disponibles")
    if not st.session_state.campanas:
        st.info("Todavía no se ha generado ninguna campaña.")
    else:
        for c in st.session_state.campanas:
            with st.expander(f"📌 {c['marca']} — {c['fecha']} ({c['motor']})"):
                st.markdown(f"**Mensaje clave:** {c['estrategia'].get('mensaje_clave')}")
                st.markdown(f"**Resumen:** {c['estrategia'].get('resumen')}")

                st.divider()
                st.write("### Entregables por red")
                cols = st.columns(len(c["redes"]))
                for idx, r in enumerate(c["redes"]):
                    with cols[idx]:
                        st.markdown(f"**{r}**")
                        if r in c["piezas"]:
                            st.image(c["piezas"][r], use_container_width=True)
                        cp = c["copys"]["copys"].get(r, {})
                        st.caption(cp.get("texto", ""))
                        st.download_button(
                            label=f"Descargar pieza {r}",
                            data=c["piezas"][r],
                            file_name=f"{slug(c['marca'])}_{slug(r)}.jpg",
                            mime="image/jpeg",
                            key=f"dl_{c['id']}_{r}"
                        )

# Tab: Equipo
with tab_equipo:
    st.subheader("Especialistas del Equipo Autónomo")
    c_eq = st.columns(3)
    for idx, m in enumerate(EQUIPO):
        with c_eq[idx % 3]:
            st.markdown(f"### {m['nombre']}")
            st.markdown(f"**{m['rol']}**")
            st.write(m["bio"])
            st.divider()

# Tab: Buscador de Talentos
with tab_buscador:
    st.subheader("Buscador de Talentos y Creadores (Javier Romero)")
    nicho_input = st.text_input("Nicho de mercado o palabra clave", value="Trading cuantitativo")
    if st.button("Buscar colaboraciones", type="secondary"):
        p_talento = f"Javier Romero (Talento). 5 perfiles recomendados de creadores de contenido para colaborar en el nicho: {nicho_input}. Formato Markdown detallado."
        with st.spinner("Javier está rastreando perfiles afines..."):
            try:
                res_talento, m_tal = ejecutar_ia(CRED, p_talento)
                st.markdown(res_talento)
                st.caption(f"Generado con: {m_tal}")
            except Exception as e:
                st.error(f"Error en la prospección: {e}")
