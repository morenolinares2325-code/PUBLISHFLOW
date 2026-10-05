import base64
import datetime
import io
import json
import os
import re
import time
import urllib.parse
import zipfile

import requests
from google import genai
from groq import Groq
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------------
# EQUIPO
# -------------------------------------------------------------------
EQUIPO = [
    {
        "id": "estrategia",
        "nombre": "Elena Navarro Ruiz",
        "rol": "Directora de Estrategia",
        "color": "#C084FC",
        "bio": "Analiza producto, mercado, publico objetivo, horarios y plan de 7 dias."
    },
    {
        "id": "copy",
        "nombre": "Marcos Vidal Herrera",
        "rol": "Copywriter Senior",
        "color": "#22D3EE",
        "bio": "Textos adaptados al limite de cada red, ganchos, variantes B y hashtags."
    },
    {
        "id": "creativa",
        "nombre": "Lucia Ortega Blanco",
        "rol": "Directora Creativa",
        "color": "#F472B6",
        "bio": "Composicion grafica por red, adaptacion de formatos y guion de video vertical."
    },
    {
        "id": "community",
        "nombre": "Daniel Soto Morales",
        "rol": "Community Manager",
        "color": "#FBBF24",
        "bio": "Publicacion directa via APIs conectadas y preparacion de descargas."
    },
    {
        "id": "analista",
        "nombre": "Sara Mendez Castillo",
        "rol": "Analista de Resultados",
        "color": "#34D399",
        "bio": "Generacion de enlaces UTM, auditoria de metricas e informes."
    },
    {
        "id": "talento",
        "nombre": "Javier Romero Gil",
        "rol": "Ojeador de Talento",
        "color": "#60A5FA",
        "bio": "Busqueda y puntuacion de creadores, afiliados y embajadores."
    }
]

EQ = {m["id"]: m for m in EQUIPO}

MARCAS = {
    "AdeskCharts": {
        "descripcion": "Plataforma avanzada de analisis tecnico y trading cuantitativo impulsada por IA.",
        "url": "https://adeskcharts.com",
        "color": "#10B981"
    },
    "SoundSnip Studio PRO": {
        "descripcion": "Suite integral de herramientas de audio inteligentes para DJs y productores.",
        "url": "https://soundsnip.studio",
        "color": "#8B5CF6"
    }
}

TIPOS = {
    "auto": "Publicacion automatica",
    "manual": "Subida manual con descarga"
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
    "TikTok": {"tipo": "manual", "tamano": (1080, 1920), "limite": 2200, "motivo": "Requiere autorizacion comercial."},
    "YouTube Shorts": {"tipo": "manual", "tamano": (1080, 1920), "limite": 1000, "motivo": "Requiere MP4 renderizado."},
    "WhatsApp": {"tipo": "manual", "tamano": (1080, 1080), "limite": 1000, "motivo": "Sin API de canales abierta."},
    "Reddit": {"tipo": "manual", "tamano": (1200, 630), "limite": 3000, "motivo": "Filtros antispam estrictos."},
    "Medium": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "API deprecada."},
    "Tumblr": {"tipo": "manual", "tamano": (1280, 1920), "limite": 4000, "motivo": "OAuth 1.0a pendiente."},
    "Hashnode": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "Integracion pendiente."},
    "Google Business": {"tipo": "manual", "tamano": (720, 540), "limite": 1500, "motivo": "Validacion fisica requerida."}
}

CONECTORES = {
    "Telegram": {
        "campos": [
            {"clave": "TELEGRAM_BOT_TOKEN", "etiqueta": "Bot Token", "secreto": True, "opcional": False, "ayuda": "De @BotFather"},
            {"clave": "TELEGRAM_CHAT_ID", "etiqueta": "Chat ID / Canal", "secreto": False, "opcional": False, "ayuda": "Canal donde el bot es admin"}
        ],
        "pasos": "1. Crea bot con @BotFather.\n2. Añadelo al canal como admin.\n3. Pon su token y el ID del canal."
    },
    "Bluesky": {
        "campos": [
            {"clave": "BLUESKY_HANDLE", "etiqueta": "Handle", "secreto": False, "opcional": False, "ayuda": "ej: usuario.bsky.social"},
            {"clave": "BLUESKY_APP_PASSWORD", "etiqueta": "App Password", "secreto": True, "opcional": False, "ayuda": "En Ajustes > Contraseñas de aplicacion"}
        ],
        "pasos": "Genera una contraseña de app en Ajustes de Bluesky."
    },
    "Discord": {
        "campos": [
            {"clave": "DISCORD_WEBHOOK_URL", "etiqueta": "Webhook URL", "secreto": True, "opcional": False, "ayuda": "URL del Webhook"}
        ],
        "pasos": "Configuracion de canal en Discord > Integraciones > Webhooks."
    },
    "Facebook": {
        "campos": [
            {"clave": "FB_PAGE_ID", "etiqueta": "ID de Pagina", "secreto": False, "opcional": False, "ayuda": "ID numerico"},
            {"clave": "FB_PAGE_TOKEN", "etiqueta": "Page Token", "secreto": True, "opcional": False, "ayuda": "Token de pagina"}
        ],
        "pasos": "Obten el token en Meta for Developers."
    },
    "Instagram": {
        "requiere": ["Facebook"],
        "campos": [
            {"clave": "IG_USER_ID", "etiqueta": "Instagram ID", "secreto": False, "opcional": False, "ayuda": "ID de cuenta vinculada a FB"}
        ],
        "pasos": "Vincula Instagram comercial a tu pagina de Facebook."
    },
    "Threads": {
        "requiere": ["Facebook"],
        "campos": [
            {"clave": "THREADS_USER_ID", "etiqueta": "Threads User ID", "secreto": False, "opcional": False, "ayuda": "ID de usuario"},
            {"clave": "THREADS_TOKEN", "etiqueta": "Threads Token", "secreto": True, "opcional": False, "ayuda": "Token de Threads"}
        ],
        "pasos": "Configura Threads API en Meta Developers."
    },
    "LinkedIn": {
        "campos": [
            {"clave": "LINKEDIN_TOKEN", "etiqueta": "Token", "secreto": True, "opcional": False, "ayuda": "Token w_member_social"},
            {"clave": "LINKEDIN_URN", "etiqueta": "Person URN", "secreto": False, "opcional": False, "ayuda": "urn:li:person:..."}
        ],
        "pasos": "Genera el token en LinkedIn Developer Portal."
    },
    "Pinterest": {
        "campos": [
            {"clave": "PINTEREST_TOKEN", "etiqueta": "Token", "secreto": True, "opcional": False, "ayuda": "Token v5"},
            {"clave": "PINTEREST_BOARD_ID", "etiqueta": "Board ID", "secreto": False, "opcional": False, "ayuda": "ID de tablero"}
        ],
        "pasos": "Obten permisos pins:write en Pinterest Developers."
    },
    "Mastodon": {
        "campos": [
            {"clave": "MASTODON_URL", "etiqueta": "Instancia", "secreto": False, "opcional": False, "ayuda": "https://mastodon.social"},
            {"clave": "MASTODON_TOKEN", "etiqueta": "Token", "secreto": True, "opcional": False, "ayuda": "Token de aplicacion"}
        ],
        "pasos": "Crea una app en Preferencias > Desarrollo de tu instancia."
    },
    "WordPress": {
        "campos": [
            {"clave": "WP_URL", "etiqueta": "URL web", "secreto": False, "opcional": False, "ayuda": "Sin / final"},
            {"clave": "WP_USER", "etiqueta": "Usuario", "secreto": False, "opcional": False, "ayuda": "Nombre de usuario"},
            {"clave": "WP_APP_PASSWORD", "etiqueta": "App Password", "secreto": True, "opcional": False, "ayuda": "En Perfil de usuario"}
        ],
        "pasos": "Genera una contraseña de aplicacion en tu perfil de WordPress."
    },
    "Dev.to": {
        "campos": [
            {"clave": "DEVTO_API_KEY", "etiqueta": "API Key", "secreto": True, "opcional": False, "ayuda": "En Settings > Extensions"}
        ],
        "pasos": "Genera la clave en las extensiones de tu cuenta de Dev.to."
    },
    "Blogger": {
        "campos": [
            {"clave": "BLOGGER_BLOG_ID", "etiqueta": "Blog ID", "secreto": False, "opcional": False, "ayuda": "ID numerico"},
            {"clave": "BLOGGER_CLIENT_ID", "etiqueta": "Client ID", "secreto": True, "opcional": False, "ayuda": "Google Cloud"},
            {"clave": "BLOGGER_CLIENT_SECRET", "etiqueta": "Client Secret", "secreto": True, "opcional": False, "ayuda": "Google Cloud"},
            {"clave": "BLOGGER_REFRESH_TOKEN", "etiqueta": "Refresh Token", "secreto": True, "opcional": False, "ayuda": "OAuth 2.0"}
        ],
        "pasos": "Habilita Blogger API v3 en Google Cloud."
    },
    "Brevo (Newsletter)": {
        "campos": [
            {"clave": "BREVO_API_KEY", "etiqueta": "API Key", "secreto": True, "opcional": False, "ayuda": "Clave v3"},
            {"clave": "BREVO_SENDER_NAME", "etiqueta": "Remitente", "secreto": False, "opcional": False, "ayuda": "Nombre remitente"},
            {"clave": "BREVO_SENDER_EMAIL", "etiqueta": "Email", "secreto": False, "opcional": False, "ayuda": "Email verificado"},
            {"clave": "BREVO_LIST_ID", "etiqueta": "List ID", "secreto": False, "opcional": False, "ayuda": "ID numerico"}
        ],
        "pasos": "Genera tu API Key en Brevo > SMTP y API."
    }
}

# -------------------------------------------------------------------
# SISTEMA DE IA MULTI-PROVEEDOR
# -------------------------------------------------------------------
_CACHE_MODELOS = {"gemini": None, "groq": None, "ts": 0}


def obtener_modelos_gemini_vivos(api_key):
    global _CACHE_MODELOS
    ahora = time.time()
    if _CACHE_MODELOS["gemini"] and (ahora - _CACHE_MODELOS["ts"] < 1800):
        return _CACHE_MODELOS["gemini"]

    try:
        client = genai.Client(api_key=api_key)
        disponibles = []
        for m in client.models.list():
            nombre = getattr(m, "name", str(m)).replace("models/", "")
            if any(x in nombre.lower() for x in ["tts", "embedding", "imagen", "veo", "whisper"]):
                continue
            metodos = getattr(m, "supported_generation_methods", []) or []
            if not metodos or "generateContent" in metodos:
                disponibles.append(nombre)

        def criterio(nom):
            n = nom.lower()
            pts = 0
            if "flash" in n:
                pts += 60
            if "lite" in n:
                pts += 20
            if "pro" in n:
                pts += 30
            nums = re.findall(r"\d+\.?\d*", n)
            if nums:
                try:
                    pts += float(nums[0]) * 10
                except ValueError:
                    pass
            return pts

        disponibles.sort(key=criterio, reverse=True)
        if disponibles:
            _CACHE_MODELOS["gemini"] = disponibles
            _CACHE_MODELOS["ts"] = ahora
            return disponibles
    except Exception:
        pass

    return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def obtener_modelos_groq_vivos(api_key):
    try:
        client = Groq(api_key=api_key)
        lista = client.models.list()
        modelos = [m.id for m in lista.data if "whisper" not in m.id.lower()]
        modelos.sort(key=lambda x: ("3.3" in x, "70b" in x, "3.1" in x, "versatile" in x), reverse=True)
        return modelos if modelos else ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    except Exception:
        return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def _ejecutar_gemini(api_key, prompt, response_schema=None):
    client = genai.Client(api_key=api_key)
    candidatos = obtener_modelos_gemini_vivos(api_key)
    ultimo_error = None

    for modelo in candidatos:
        try:
            config = {}
            if response_schema:
                config["response_mime_type"] = "application/json"
                config["response_schema"] = response_schema
            resp = client.models.generate_content(
                model=modelo, contents=prompt, config=config if config else None
            )
            if resp.text:
                return resp.text, f"Gemini ({modelo})"
        except Exception as e:
            err = str(e).lower()
            ultimo_error = e
            if any(k in err
