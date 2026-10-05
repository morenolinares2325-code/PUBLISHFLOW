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
# CONFIGURACIÓN GENERAL Y ESTILO NEÓN
# ---------------------------------------------------------
st.set_page_config(
    page_title="PublishFlow Agencia",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0b0714;
        color: #f3f4f6;
    }
    .card-empleado {
        background: #140d24;
        border: 1px solid #2d1f4d;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .card-empleado:hover {
        border-color: #a855f7;
        transform: translateY(-2px);
    }
    .card-empleado h3 {
        margin-top: 14px;
        margin-bottom: 4px;
        font-size: 1.2rem;
        color: #f3f4f6;
    }
    .badge-rol {
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: inline-block;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# EQUIPO (RUTAS LOCALES A fotos/)
# ---------------------------------------------------------
EQUIPO = [
    {
        "id": "estrategia",
        "nombre": "Elena Navarro Ruiz",
        "rol": "Directora de Estrategia",
        "color": "#C084FC",
        "foto": "fotos/elena.jpg",
        "bio": "Analiza producto, mercado, público objetivo, horarios de impacto y plan de 7 días."
    },
    {
        "id": "copy",
        "nombre": "Marcos Vidal Herrera",
        "rol": "Copywriter Senior",
        "color": "#22D3EE",
        "foto": "fotos/marcos.jpg",
        "bio": "Textos adaptados al límite de cada red, ganchos persuasivos, variantes B y hashtags."
    },
    {
        "id": "creativa",
        "nombre": "Lucía Ortega Blanco",
        "rol": "Directora Creativa",
        "color": "#F472B6",
        "foto": "fotos/lucia.jpg",
        "bio": "Composición gráfica por red, adaptación de formatos y guion técnico para vídeo vertical."
    },
    {
        "id": "community",
        "nombre": "Daniel Soto Morales",
        "rol": "Community Manager",
        "color": "#FBBF24",
        "foto": "fotos/daniel.jpg",
        "bio": "Publicación directa vía APIs conectadas y preparación de assets para descarga."
    },
    {
        "id": "analista",
        "nombre": "Sara Méndez Castillo",
        "rol": "Analista de Resultados",
        "color": "#34D399",
        "foto": "fotos/sara.jpg",
        "bio": "Generación de enlaces UTM, auditoría de métricas e informes de rendimiento."
    },
    {
        "id": "talento",
        "nombre": "Javier Romero Gil",
        "rol": "Ojeador de Talento",
        "color": "#60A5FA",
        "foto": "fotos/javier.jpg",
        "bio": "Búsqueda y puntuación de creadores, microinfluencers y afiliados del sector."
    }
]

MARCAS = {
    "AdeskCharts": {
        "descripcion": "Plataforma avanzada de análisis técnico y trading cuantitativo impulsada por IA.",
        "url": "https://adeskcharts.com",
        "color": "#10B981"
    },
    "SoundSnip Studio PRO": {
        "descripcion": "Suite integral de herramientas de audio inteligentes para DJs y productores.",
        "url": "https://soundsnip.studio",
        "color": "#8B5CF6"
    }
}

REDES = {
    "Telegram": {"tamano": (1200, 800), "limite": 1024},
    "Bluesky": {"tamano": (1200, 675), "limite": 300},
    "Discord": {"tamano": (1200, 675), "limite": 2000},
    "Facebook": {"tamano": (1200, 630), "limite": 2000},
    "Instagram": {"tamano": (1080, 1080), "limite": 2200},
    "Threads": {"tamano": (1080, 1080), "limite": 500},
    "LinkedIn": {"tamano": (1200, 627), "limite": 3000},
    "Pinterest": {"tamano": (1000, 1500), "limite": 500},
    "Mastodon": {"tamano": (1200, 675), "limite": 500},
    "WordPress": {"tamano": (1200, 630), "limite": 10000},
    "Dev.to": {"tamano": (1000, 420), "limite": 10000}
}

CONECTORES = {
    "Telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "Bluesky": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
    "Discord": ["DISCORD_WEBHOOK_URL"],
    "Dev.to": ["DEVTO_API_KEY"]
}

# ---------------------------------------------------------
# FUNCIONES AUXILIARES Y FOTOS
# ---------------------------------------------------------
def obtener_avatar_html(ruta_foto, tamano=110):
    if os.path.exists(ruta_foto):
        try:
            with open(ruta_foto, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                return f'<img src="data:image/jpeg;base64,{b64}" style="width:{tamano}px; height:{tamano}px; border-radius:50%; object-fit:cover; border:2px solid #a855f7; display:block; margin:0 auto; box-shadow:0 0 10px rgba(168,85,247,0.3);" />'
        except Exception:
            pass
    return f'<div style="width:{tamano}px; height:{tamano}px; border-radius:50%; background:#2d1f4d; color:#c084fc; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:36px; border:2px solid #a855f7;">👤</div>'

def slug(txt):
    s = re.sub(r"[^\w\s-]", "", txt).strip().lower()
    return re.sub(r"[-\s]+", "_", s)

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

    overlay = Image.new("RGBA", (w, h), (15, 8, 30, 130))
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
# SISTEMA DE IA MULTI-PROVEEDOR (3 NIVELES)
# ---------------------------------------------------------
def ejecutar_ia(credenciales, prompt, response_schema=None):
    errores = []

    k1 = credenciales.get("GEMINI_FREE_KEY") or credenciales.get("GEMINI_API_KEY")
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

    k2 = credenciales.get("GROQ_API_KEY")
    if k2:
        try:
            client = Groq(api_key=k2)
            p_final = prompt
            if response_schema:
                p_final = f"{prompt}\n\nResponde ÚNICAMENTE en JSON válido con este esquema:\n{json.dumps(response_schema)}"
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

    k3 = credenciales.get("GEMINI_PAID_KEY")
    if k3:
        try:
            client = genai.Client(api_key=k3)
            cfg = {"response_mime_type": "application/json", "response_schema": response_schema} if response_schema else None
            res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
            if res.text:
                return res.text, "🔴 Nivel 3 [Gemini Paid]"
        except Exception as e:
            errores.append(f"Gemini Paid: {e}")

    raise RuntimeError("Todas las opciones de IA fallaron:\n" + "\n".join(errores))

# ---------------------------------------------------------
# CREDENCIALES
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
    st.write(f"Nivel 1 (Gemini): {'🟢 Activo' if CRED['GEMINI_FREE_KEY'] else '⚪ Desactivado'}")
    st.write(f"Nivel 2 (Groq): {'🟡 Activo' if CRED['GROQ_API_KEY'] else '⚪ Desactivado'}")
    st.write(f"Nivel 3 (Paid): {'🔴 Activo' if CRED['GEMINI_PAID_KEY'] else '⚪ Desactivado'}")

    st.divider()
    redes_activas = [r for r, llaves in CONECTORES.items() if all(CRED.get(k) for k in llaves)]
    st.subheader("Redes Conectadas")
    st.write(f"🟢 {len(redes_activas)} de {len(CONECTORES)} configuradas")

# Pestañas principales
tab_nuevo, tab_historial, tab_equipo, tab_buscador = st.tabs([
    "📋 Nuevo Encargo",
    "📁 Campañas Guardadas",
    "👥 Equipo",
    "🔍 Buscador de Talentos"
])

# Tab 1: Nuevo Encargo
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

                    # Guardar campaña
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

# Tab 2: Campañas Guardadas
with tab_historial:
    st.subheader("Historial de Entregas")
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

# Tab 3: Equipo con Fotos
with tab_equipo:
    st.subheader("Especialistas del Equipo Autónomo")
    st.write("Profesionales de IA dedicados al crecimiento orgánico de tus marcas:")
    
    cols = st.columns(3)
    for idx, m in enumerate(EQUIPO):
        with cols[idx % 3]:
            avatar_html = obtener_avatar_html(m["foto"])
            st.markdown(f"""
            <div class="card-empleado">
                {avatar_html}
                <h3>{m['nombre']}</h3>
                <span class="badge-rol" style="color:{m['color']};">{m['rol']}</span>
                <p style="font-size: 0.88rem; color: #9ca3af; margin-top: 6px;">{m['bio']}</p>
            </div>
            """, unsafe_allow_html=True)

# Tab 4: Buscador de Talentos
with tab_buscador:
    st.subheader("Buscador de Talentos y Creadores (Javier Romero)")
    nicho_input = st.text_input("Nicho o sector de búsqueda", value="Trading cuantitativo y algorithmic trading")
    if st.button("Buscar colaboraciones con IA", type="secondary"):
        p_talento = f"Javier Romero (Talento). 5 perfiles recomendados de creadores de contenido para colaborar en el nicho: {nicho_input}. Formato Markdown detallado con canal, afinidad y mensaje de contacto."
        with st.spinner("Javier está prospectando colaboraciones..."):
            try:
                res_talento, m_tal = ejecutar_ia(CRED, p_talento)
                st.markdown(res_talento)
                st.caption(f"Generado con: {m_tal}")
            except Exception as e:
                st.error(f"Error en la prospección: {e}")
