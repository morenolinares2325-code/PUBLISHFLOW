import os
import time
import requests
from PIL import Image
import io
from bs4 import BeautifulSoup
import streamlit as st
from google import genai
from google.genai.errors import APIError

# Lista de modelos estables y activos según el catálogo oficial
MODELOS_VALIDOS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash"
]

def get_gemini_client():
    """Obtiene el cliente del SDK oficial google-genai."""
    key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if isinstance(key, str):
        key = key.strip().strip('"').strip("'")
    
    if not key:
        st.error("🔑 **Error de Clave API:** No se encontró `GEMINI_API_KEY` en los Secrets de Streamlit.")
        st.stop()
    
    return genai.Client(api_key=key)

def call_gemini_with_fallback_and_retry(client, contents, retries_per_model=3):
    """
    Recorre los modelos activos en orden de prioridad.
    Maneja saturación (503) con esperas progresivas y salta
    automáticamente si un modelo da error.
    """
    last_error = None

    for model_name in MODELOS_VALIDOS:
        for attempt in range(retries_per_model):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    return response
            except APIError as e:
                last_error = e
                err_str = str(e)
                # Si el modelo da error de endpoint o argumento, saltar al siguiente modelo
                if getattr(e, 'code', None) in [404, 400] or "NOT_FOUND" in err_str or "INVALID_ARGUMENT" in err_str:
                    break
                # Para saturación (503) o límite de cuota (429), esperar progresivamente (2s, 4s, 6s)
                time.sleep((attempt + 1) * 2)
            except Exception as e:
                last_error = e
                time.sleep((attempt + 1) * 2)

    if last_error:
        raise last_error
    else:
        raise RuntimeError("No se pudo obtener respuesta de ningún modelo de Gemini.")

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
    """Genera publicaciones adaptadas para redes sociales junto con un prompt de imagen IA."""
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
    
    INSTRUCCIONES DE FORMATO Y ESTRUCTURA:
    1. Genera el contenido adaptado específicamente a cada red elegida ({platforms_str}).
    2. Usa emojis adecuados al tono seleccionado.
    3. Etiqueta y separa claramente la sección de cada red social usando encabezados (ej. ### Instagram, ### LinkedIn, ### X (Twitter)).
    4. Al final del documento, añade una sección especial llamada:
       ### 🎨 Prompt Recomendado para Imagen IA (Midjourney / DALL-E)
       Escribe un prompt detallado en INGLÉS para generar una imagen impactante que acompañe a estas publicaciones.
    """

    text_response = call_gemini_with_fallback_and_retry(client, prompt)
    return text_response.text

def analyze_product_and_generate_strategy(product_image_bytes, target_location: str, target_audience: str, tone: str = "Profesional", language: str = "Español"):
    """Analiza la imagen de un producto o vehículo procesada con PIL Image."""
    client = get_gemini_client()
    image = Image.open(io.BytesIO(product_image_bytes))

    prompt = f"""
    Eres un experto en Growth Hacking y Social Media Marketing.
    Analiza detalladamente la foto adjunta de este producto o vehículo.
    
    PARÁMETROS:
    - Ubicación Objetivo: {target_location}
    - Público Objetivo: {target_audience}
    - Tono del Copy: {tone}
    - Idioma: {language}

    Genera una estrategia completa estructurada en los siguientes puntos:
    ### 📝 Copy Comercial A (Enfoque Beneficios y Emoción)
    ### 📝 Copy Comercial B (Enfoque Oferta Directa y Llamada a la Acción)
    ### 📍 3 Ubicaciones Clave para Etiquetar en {target_location}
    ### ⏰ Días y Horarios Picos de Publicación
    ### 🏷️ Lista de Hashtags de Alto Impacto
    ### 👁️ Texto Alternativo (SEO / Alt-Text para la imagen)
    """

    response = call_gemini_with_fallback_and_retry(client, [image, prompt])
    return response.text

def generate_weekly_calendar(topic_or_url: str, language: str = "Español", tone: str = "Profesional"):
    """Genera un plan/calendario editorial completo de 7 días."""
    client = get_gemini_client()

    extracted_text = ""
    if topic_or_url.startswith("http://") or topic_or_url.startswith("https://"):
        extracted_text = fetch_url_content(topic_or_url)

    context = extracted_text if extracted_text else topic_or_url

    prompt = f"""
    Eres un estratega de contenidos para redes sociales.
    Crea un Calendario Editorial de 7 días (Lunes a Domingo) enfocado en la siguiente temática u origen:
    "{context}"

    PARÁMETROS:
    - Idioma: {language}
    - Tono de voz: {tone}

    FORMATO REQUERIDO:
    Para cada día (Lunes, Martes, Miércoles, Jueves, Viernes, Sábado, Domingo) incluye:
    - **Día y Objetivo:** (Ej. Lunes - Valor Educativo / Viernes - Promocional)
    - **Idea del Post / Titular:**
    - **Formato Recomendado:** (Ej. Carrusel, Reel/Video corto, Texto + Foto, Hilo)
    - **Llamada a la Acción (CTA):**
    """

    response = call_gemini_with_fallback_and_retry(client, prompt)
    return response.text
