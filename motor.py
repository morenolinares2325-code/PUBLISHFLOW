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
        "bio": "Analiza producto, mercado, público objetivo, horarios de impacto y plan de 7 días."
    },
    {
        "id": "copy",
        "nombre": "Marcos Vidal Herrera",
        "rol": "Copywriter Senior",
        "color": "#22D3EE",
        "bio": "Textos adaptados al límite de cada red, ganchos de impacto, variantes B y hashtags."
    },
    {
        "id": "creativa",
        "nombre": "Lucía Ortega Blanco",
        "rol": "Directora Creativa",
        "color": "#F472B6",
        "bio": "Composición gráfica por red, adaptación de formatos y guion técnico para vídeo vertical."
    },
    {
        "id": "community",
        "nombre": "Daniel Soto Morales",
        "rol": "Community Manager",
        "color": "#FBBF24",
        "bio": "Publicación directa vía APIs conectadas y preparación de assets para subida manual."
    },
    {
        "id": "analista",
        "nombre": "Sara Méndez Castillo",
        "rol": "Analista de Resultados",
        "color": "#34D399",
        "bio": "Generación de enlaces UTM, auditoría de métricas e informes de rendimiento comercial."
    },
    {
        "id": "talento",
        "nombre": "Javier Romero Gil",
        "rol": "Ojeador de Talento",
        "color": "#60A5FA",
        "bio": "Búsqueda y puntuación de creadores, microinfluencers y afiliados del sector."
    }
]

EQ = {m["id"]: m for m in EQUIPO}

# -------------------------------------------------------------------
# MARCAS
# -------------------------------------------------------------------
MARCAS = {
    "AdeskCharts": {
        "descripcion": "Plataforma avanzada de análisis técnico y trading cuantitativo impulsada por IA. Generación y optimización de estrategias, alertas algorítmicas y backtesting en tiempo real.",
        "url": "https://adeskcharts.com",
        "color": "#10B981"
    },
    "SoundSnip Studio PRO": {
        "descripcion": "Suite integral de herramientas de audio inteligentes para DJs, beatmakers y productores. Detección armónica, edición rápida de transiciones y procesado algorítmico.",
        "url": "https://soundsnip.studio",
        "color": "#8B5CF6"
    }
}

TIPOS = {
    "auto": "Publicación automática",
    "manual": "Subida manual con descarga"
}

# -------------------------------------------------------------------
# ESPECIFICACIÓN DE REDES
# -------------------------------------------------------------------
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
    "X (Twitter)": {"tipo": "manual", "tamano": (1200, 675), "limite": 280, "motivo": "API de escritura de pago."},
    "TikTok": {"tipo": "manual", "tamano": (1080, 1920), "limite": 2200, "motivo": "Requiere verificación comercial por app."},
    "YouTube Shorts": {"tipo": "manual", "tamano": (1080, 1920), "limite": 1000, "motivo": "Requiere archivo MP4 renderizado."},
    "WhatsApp": {"tipo": "manual", "tamano": (1080, 1080), "limite": 1000, "motivo": "Los canales broadcast no ofrecen API abierta."},
    "Reddit": {"tipo": "manual", "tamano": (1200, 630), "limite": 3000, "motivo": "Filtros antispam estrictos contra bots."},
    "Medium": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "API de publicación legacy cerrada a nuevas apps."},
    "Tumblr": {"tipo": "manual", "tamano": (1280, 1920), "limite": 4000, "motivo": "Flujo OAuth 1.0a pendiente."},
    "Hashnode": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "Integración GraphQL pendiente."},
    "Google Business": {"tipo": "manual", "tamano": (720, 540), "limite": 1500, "motivo": "Exige validación de localización física."}
}

# -------------------------------------------------------------------
# ESPECIFICACIÓN DE CONECTORES
# -------------------------------------------------------------------
CONECTORES = {
    "Telegram": {
        "campos": [
            {"clave": "TELEGRAM_BOT_TOKEN", "etiqueta": "Bot Token", "secreto": True, "opcional": False, "ayuda": "Obtenido de @BotFather"},
            {"clave": "TELEGRAM_CHAT_ID", "etiqueta": "Chat ID / Canal (@nombre o -100...)", "secreto": False, "opcional": False, "ayuda": "El bot debe ser administrador"}
        ],
        "pasos": "1. Habla con @BotFather en Telegram y crea un bot con /newbot.\n2. Copia el token.\n3. Añade el bot como administrador en tu canal.\n4. Introduce el @nombre o ID numérico del canal."
    },
    "Bluesky": {
        "campos": [
            {"clave": "BLUESKY_HANDLE", "etiqueta": "Handle (ej: usuario.bsky.social)", "secreto": False, "opcional": False, "ayuda": "Tu identificador en Bluesky"},
            {"clave": "BLUESKY_APP_PASSWORD", "etiqueta": "App Password", "secreto": True, "opcional": False, "ayuda": "Generada en Configuración > Contraseñas de aplicación"}
        ],
        "pasos": "1. Ve a Ajustes en Bluesky > Privacidad y seguridad > Contraseñas de la aplicación.\n2. Crea una nueva contraseña específica para PublishFlow y pégala aquí."
    },
    "Discord": {
        "campos": [
            {"clave": "DISCORD_WEBHOOK_URL", "etiqueta": "Webhook URL", "secreto": True, "opcional": False, "ayuda": "URL generada en la configuración del canal"}
        ],
        "pasos": "1. En tu servidor de Discord, entra en la configuración del canal > Integraciones > Webhooks.\n2. Pulsa 'Nuevo Webhook', copia la URL y pégala aquí."
    },
    "Facebook": {
        "campos": [
            {"clave": "FB_PAGE_ID", "etiqueta": "ID de la Página", "secreto": False, "opcional": False, "ayuda": "ID numérico de la página de fans"},
            {"clave": "FB_PAGE_TOKEN", "etiqueta": "Token de acceso de la página", "secreto": True, "opcional": False, "ayuda": "Token de larga duración de Meta Graph"}
        ],
        "pasos": "1. Accede a Meta for Developers y obtén un User Token con permisos pages_manage_posts.\n2. Canjéalo por un Page Access Token permanente."
    },
    "Instagram": {
        "requiere": ["Facebook"],
        "campos": [
            {"clave": "IG_USER_ID", "etiqueta": "Instagram Professional ID", "secreto": False, "opcional": False, "ayuda": "ID de la cuenta comercial conectada a la página de Facebook"}
        ],
        "pasos": "1. Conecta primero Facebook.\n2. Asegúrate de que la cuenta de Instagram sea comercial o creador y esté vinculada a la página de Facebook."
    },
    "Threads": {
        "requiere": ["Facebook"],
        "campos": [
            {"clave": "THREADS_USER_ID", "etiqueta": "Threads User ID", "secreto": False, "opcional": False, "ayuda": "ID de usuario de Threads API"},
            {"clave": "THREADS_TOKEN", "etiqueta": "Threads Token", "secreto": True, "opcional": False, "ayuda": "Token de larga duración de Threads"}
        ],
        "pasos": "1. Configura una app en Meta Developer Dashboard con el caso de uso 'Threads API'.\n2. Genera el token de usuario."
    },
    "LinkedIn": {
        "campos": [
            {"clave": "LINKEDIN_TOKEN", "etiqueta": "OAuth Access Token", "secreto": True, "opcional": False, "ayuda": "Token con permiso w_member_social"},
            {"clave": "LINKEDIN_URN", "etiqueta": "Person URN (ej: urn:li:person:XXXX)", "secreto": False, "opcional": False, "ayuda": "Identificador único de perfil"}
        ],
        "pasos": "1. Crea una app en LinkedIn Developer Portal con el producto 'Share on LinkedIn'.\n2. Autentica y genera un token con alcance w_member_social."
    },
    "Pinterest": {
        "campos": [
            {"clave": "PINTEREST_TOKEN", "etiqueta": "Access Token", "secreto": True, "opcional": False, "ayuda": "Token de API v5 con permisos de escritura"},
            {"clave": "PINTEREST_BOARD_ID", "etiqueta": "Board ID", "secreto": False, "opcional": False, "ayuda": "ID del tablero donde publicar"}
        ],
        "pasos": "1. Accede al portal de desarrolladores de Pinterest.\n2. Crea un token con alcance boards:read,pins:write y obtén el ID del tablero destino."
    },
    "Mastodon": {
        "campos": [
            {"clave": "MASTODON_URL", "etiqueta": "URL de la instancia (ej: https://mastodon.social)", "secreto": False, "opcional": False, "ayuda": "Instancia donde reside tu cuenta"},
            {"clave": "MASTODON_TOKEN", "etiqueta": "Access Token", "secreto": True, "opcional": False, "ayuda": "Token con permisos write:statuses y write:media"}
        ],
        "pasos": "1. En tu instancia de Mastodon, ve a Preferencias > Desarrollo > Nueva aplicación.\n2. Selecciona permisos de lectura y escritura (write:statuses, write:media) y copia el Access Token."
    },
    "WordPress": {
        "campos": [
            {"clave": "WP_URL", "etiqueta": "URL del sitio (ej: https://miweb.com)", "secreto": False, "opcional": False, "ayuda": "Sin barra final"},
            {"clave": "WP_USER", "etiqueta": "Usuario Administrador / Editor", "secreto": False, "opcional": False, "ayuda": "Nombre de usuario"},
            {"clave": "WP_APP_PASSWORD", "etiqueta": "Contraseña de aplicación", "secreto": True, "opcional": False, "ayuda": "Generada en Perfil de usuario"}
        ],
        "pasos": "1. Entra a tu panel de WordPress > Usuarios > Perfil.\n2. Ve a 'Contraseñas de aplicación', asigna un nombre y genera una nueva contraseña."
    },
    "Dev.to": {
        "campos": [
            {"clave": "DEVTO_API_KEY", "etiqueta": "API Key", "secreto": True, "opcional": False, "ayuda": "Generada en Settings > Extensions"}
        ],
        "pasos": "1. En Dev.to, ve a Settings > Extensions > DEV Community API Keys.\n2. Genera una nueva clave y pégala aquí."
    },
    "Blogger": {
        "campos": [
            {"clave": "BLOGGER_BLOG_ID", "etiqueta": "Blog ID", "secreto": False, "opcional": False, "ayuda": "ID numérico en la URL de Blogger"},
            {"clave": "BLOGGER_CLIENT_ID", "etiqueta": "Client ID", "secreto": True, "opcional": False, "ayuda": "Google Cloud Console"},
            {"clave": "BLOGGER_CLIENT_SECRET", "etiqueta": "Client Secret", "secreto": True, "opcional": False, "ayuda": "Google Cloud Console"},
            {"clave": "BLOGGER_REFRESH_TOKEN", "etiqueta": "Refresh Token", "secreto": True, "opcional": False, "ayuda": "OAuth 2.0 refresh token"}
        ],
        "pasos": "1. Habilita Blogger API v3 en Google Cloud Console.\n2. Configura pantalla OAuth y genera un Refresh Token con permisos de escritura."
    },
    "Brevo (Newsletter)": {
        "campos": [
            {"clave": "BREVO_API_KEY", "etiqueta": "API v3 Key", "secreto": True, "opcional": False, "ayuda": "Clave de API de Brevo"},
            {"clave": "BREVO_SENDER_NAME", "etiqueta": "Nombre del remitente", "secreto": False, "opcional": False, "ayuda": "Ej: Equipo PublishFlow"},
            {"clave": "BREVO_SENDER_EMAIL", "etiqueta": "Email remitente", "secreto": False, "opcional": False, "ayuda": "Email autenticado en Brevo"},
            {"clave": "BREVO_LIST_ID", "etiqueta": "ID de Lista Destino", "secreto": False, "opcional": False, "ayuda": "ID numérico de la lista de contactos"}
        ],
        "pasos": "1. En Brevo, ve a Configuración de cuenta > SMTP y API > Claves API y genera una v3.\n2. Indica el remitente verificado y la lista de destino."
    }
}

# -------------------------------------------------------------------
# SISTEMA DE IA INTELIGENTE: AUTO-DESCUBRIMIENTO Y 3 NIVELES
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
            nombre = m.
