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
        "descripcion": "Plataforma avanzada de analisis tecnico y trading cuantitativo con IA.",
        "url": "https://adeskcharts.com",
        "color": "#10B981"
    },
    "SoundSnip Studio PRO": {
        "descripcion": "Suite de herramientas inteligentes de audio para DJs y productores.",
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
    "YouTube Shorts": {"tipo": "manual", "tamano": (1080, 1920), "limite": 1000, "motivo": "Requiere MP4."},
    "WhatsApp": {"tipo": "manual", "tamano": (1080, 1080), "limite": 1000, "motivo": "Sin API de canales."},
    "Reddit": {"tipo": "manual", "tamano": (1200, 630), "limite": 3000, "motivo": "Antispam estricto."},
    "Medium": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "API deprecada."},
    "Tumblr": {"tipo": "manual", "tamano": (1280, 1920), "limite": 4000, "motivo": "Pendiente."},
    "Hashnode": {"tipo": "manual", "tamano": (1200, 630), "limite": 10000, "motivo": "Pendiente."},
    "Google Business": {"tipo": "manual", "tamano": (720, 540), "limite": 1500, "motivo": "Validacion fisica requerida."}
}

CONECTORES = {
    "Telegram": {
        "campos": [
            {"clave": "TELEGRAM_BOT_TOKEN", "etiqueta": "Bot Token", "secreto": True, "opcional": False, "ayuda": "De @BotFather"},
            {"clave": "TELEGRAM_CHAT_ID", "etiqueta": "Chat ID / Canal", "secreto": False, "opcional": False, "ayuda": "Canal donde el bot es admin"}
        ],
        "pasos": "1. Crea bot con @BotFather.\n2. Añadelo al canal como admin.\n3.
