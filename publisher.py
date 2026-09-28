import os
import requests
from PIL import Image
import io
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def get_gemini_client(api_key: str = None):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("No se encontró la GEMINI_API_KEY.")
    return genai.Client(api_key=key)

def fetch_url_content(url: str) -> str:
    """Extrae texto relevante de una URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = [p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])]
            return ' '.join(paragraphs)[:2000]
    except Exception as e:
        print(f"Error al analizar la URL: {e}")
    return ""

def generate_multi_platform_content(source_input: str, target_platforms: list, api_key: str = None):
    """Genera copys multired e imagen conceptual con Gemini."""
    client = get_gemini_client(api_key)

    extracted_text = ""
    if source_input.startswith("http://") or source_input.startswith("https://"):
        extracted_text = fetch_url_content(source_input)

    context = extracted_text if extracted_text else source_input
    platforms_str = ", ".join(target_platforms)

    text_prompt = f"""
    Eres un Social Media Manager profesional. Genera contenido para las siguientes redes sociales: {platforms_str}.
    
    Información / Tema: "{context}"
    
    Instrucciones:
    - Adapta el formato y tono a cada red (LinkedIn profesional, X/Twitter corto, Instagram dinámico con hashtags/emojis).
    - Etiqueta claramente cada sección (ej. ### Instagram, ### LinkedIn).
    """

    text_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=text_prompt
    )

    image_prompt = f"Una ilustración promocional profesional para redes sociales sobre: {source_input[:150]}"
    image_response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=image_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1")
        )
    )

    image_bytes = None
    for part in image_response.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            break

    return text_response.text, image_bytes

def analyze_product_and_generate_strategy(product_image_bytes, target_location: str, target_audience: str, api_key: str = None):
    """Analiza la foto real de un producto y sugiere copys, horarios y hashtags."""
    client = get_gemini_client(api_key)
    image = Image.open(io.BytesIO(product_image_bytes))

    prompt = f"""
    Eres un experto en Growth Hacking y Social Media.
    Analiza detalladamente la foto adjunta de este producto.
    - Ubicación Objetivo: {target_location}
    - Público Objetivo: {target_audience}

    Genera una estrategia completa con estos apartados:
    ### 📝 Copy Comercial (Modelo AIDA)
    ### 📍 Ubicación Estratégica Sugerida (3 ubicaciones en {target_location})
    ### ⏰ Mejor Día y Horario de Publicación
    ### 🏷️ Hashtags de Alto Impacto
    ### 👁️ Texto Alternativo (SEO/Alt-Text)
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image, prompt]
    )

    return response.text
