import os
import time
import requests
from PIL import Image
import io
from bs4 import BeautifulSoup
import streamlit as st
from google import genai

# Usamos el modelo ultraestable 1.5-flash
MODEL_NAME = 'gemini-1.5-flash'

def get_gemini_client():
    key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    key = str(key).strip().strip('"').strip("'")
    
    if not key:
        raise ValueError("No se encontró la GEMINI_API_KEY en los Secrets de Streamlit.")
    
    return genai.Client(api_key=key)

def call_gemini_until_success(client, model, contents, delay=2):
    """Reintenta indefinidamente en bucle hasta que la API responda con éxito."""
    attempt = 1
    while True:
        try:
            return client.models.generate_content(model=model, contents=contents)
        except Exception as e:
            # Espera 2 segundos y vuelve a intentar automáticamente
            time.sleep(delay)
            attempt += 1

def fetch_url_content(url: str) -> str:
    """Extrae texto de una URL dada."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = [p.get_text() for p in soup.find_all(['h1', 'h2', 'p'])]
            return ' '.join(paragraphs)[:1500]
    except Exception:
        pass
    return ""

def generate_multi_platform_content(source_input: str, target_platforms: list, tone: str = "Profesional", language: str = "Español", post_style: str = "Estándar", hashtag_count: int = 10):
    """Genera publicaciones adaptadas para redes sociales usando Gemini."""
    client = get_gemini_client()

    extracted_text = ""
    if source_input.startswith("http://") or source_input.startswith("https://"):
        extracted_text = fetch_url_content(source_input)

    context = extracted_text if extracted_text else source_input
    platforms_str = ", ".join(target_platforms)

    prompt = f"""
    Eres un Social Media Manager y Copywriter experto. Genera publicaciones optimizadas para las siguientes redes: {platforms_str}.
    
    INFORMACIÓN DE ORIGEN / TEMA:
    "{context}"
    
    PARÁMETROS DE CONFIGURACIÓN:
    - Idioma: {language}
    - Tono de voz: {tone}
    - Estilo/Estructura del post: {post_style}
    - Cantidad máxima de hashtags al final: {hashtag_count}
    
    INSTRUCCIONES DE FORMATO:
    - Genera el contenido adaptado específicamente a cada red elegida ({platforms_str}).
    - Usa emojis adecuados al tono seleccionado.
    - Etiqueta y separa claramente la sección de cada red social usando encabezados (ej. ### Instagram, ### LinkedIn, ### X (Twitter)).
    """

    text_response = call_gemini_until_success(client, MODEL_NAME, prompt)
    return text_response.text

def analyze_product_and_generate_strategy(product_image_bytes, target_location: str, target_audience: str, tone: str = "Profesional", language: str = "Español"):
    """Analiza la imagen real de un producto y genera estrategia comercial."""
    client = get_gemini_client()
    image = Image.open(io.BytesIO(product_image_bytes))

    prompt = f"""
    Eres un experto en Growth Hacking y Social Media Marketing.
    Analiza detalladamente la foto adjunta de este producto.
    
    PARÁMETROS:
    - Ubicación Objetivo: {target_location}
    - Público Objetivo: {target_audience}
    - Tono del Copy: {tone}
    - Idioma: {language}

    Genera una estrategia completa estructurada en los siguientes puntos:
    ### 📝 Copy Comercial Persuasivo
    ### 📍 3 Ubicaciones Clave para Etiquetar en {target_location}
    ### ⏰ Días y Horarios Picos de Publicación
    ### 🏷️ Lista de Hashtags de Alto Impacto
    ### 👁️ Texto Alternativo (SEO / Alt-Text para la imagen)
    """

    response = call_gemini_until_success(client, MODEL_NAME, [image, prompt])
    return response.text
