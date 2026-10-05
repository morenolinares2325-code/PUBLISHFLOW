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
# CONFIGURACIÓN GENERAL Y ESTILO
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
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .card-empleado h3 {
        margin-top: 10px;
        margin-bottom: 4px;
        font-size: 1.15rem;
    }
    .badge-rol {
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# EQUIPO CON RUTAS DE FOTO
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
    "TikTok": {"tipo": "manual", "tamano": (1080, 1920), "limite": 2200, "motivo": "Verificación comercial."},
    "YouTube Shorts": {"tipo": "manual", "tamano": (1080, 1920), "limite": 1000, "motivo": "Requiere MP4."},
    "WhatsApp": {"tipo": "manual", "tamano": (1080, 1080), "limite": 1000, "motivo": "Canales cerrados."},
    "Reddit": {"tipo": "manual", "tamano": (1200, 630), "limite": 3000, "motivo": "Antispam."},
    "Medium": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "API cerrada."},
    "Tumblr": {"tipo": "manual", "tamano": (1280, 1920), "limite": 4000, "motivo": "OAuth 1.0a."},
    "Hashnode": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "GraphQL."},
    "Google Business": {"tipo": "manual", "tamano": (720, 540), "limite": 1500, "motivo": "Física."}
}

CONECTORES = {
    "Telegram": {"campos": [{"clave": "TELEGRAM_BOT_TOKEN", "opcional": False}, {"clave": "TELEGRAM_CHAT_ID", "opcional": False}]},
    "Bluesky": {"campos": [{"clave": "BLUESKY_HANDLE", "opcional": False}, {"clave": "BLUESKY_APP_PASSWORD", "opcional": False}]},
    "Discord": {"campos": [{"clave": "DISCORD_WEBHOOK_URL", "opcional": False}]},
    "Dev.to": {"campos": [{"clave": "DEVTO_API_KEY", "opcional": False}]}
}

# ---------------------------------------------------------
# HELPER DE IMÁGENES Y AVATARES
# ---------------------------------------------------------
def obtener_avatar_html(ruta_foto, tamano=100):
    if os.path.exists(ruta_foto):
        try:
            with open(ruta_foto, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
                return f'<img src="data:image/jpeg;base64,{data}" style="width:{tamano}px; height:{tamano}px; border-radius:50%; object-fit:cover; border:2px solid #a855f7; display:block; margin:0 auto;" />'
        except Exception:
            pass
    return f'<div style="width:{tamano}px; height:{tamano}px; border-radius:50%; background:#2d1f4d; color:#c084fc; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:32px;">👤</div>'

# ---------------------------------------------------------
# SISTEMA DE IA EN CASCADA
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

    k3 = credenciales.get("GEMINI_PAID_KEY")
