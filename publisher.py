import os
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def fetch_url_content(url: str) -> str:
    """Extrae el texto relevante de una página web dada su URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extraer títulos y párrafos principales
            paragraphs = [p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])]
            text_content = ' '.join(paragraphs)
            return text_content[:2000] # Limitar longitud para el prompt
    except Exception as e:
        print(f"Error al analizar la URL: {e}")
    return ""

def get_gemini_client(api_key: str = None):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("No se encontró la GEMINI_API_KEY.")
    return genai.Client(api_key=key)

def generate_multi_platform_content(source_input: str, target_platforms: list, api_key: str = None):
    """
    Genera publicaciones adaptadas para múltiples redes y una imagen conceptual.
    source_input puede ser una URL o un tema directo.
    """
    client = get_gemini_client(api_key)

    # Si es una URL, extraer información de la página
    extracted_text = ""
    if source_input.startswith("http://") or source_input.startswith("https://"):
        extracted_text = fetch_url_content(source_input)

    context = extracted_text if extracted_text else source_input
    platforms_str = ", ".join(target_platforms)

    # 1. Redacción del Copy Multired
    text_prompt = f"""
    Eres un Social Media Manager profesional. Genera contenido para las siguientes redes sociales: {platforms_str}.
    
    Información de origen / Marca / Tema:
    "{context}"
    
    Instrucciones:
    - Genera un texto adaptado específicamente al formato y tono de cada red seleccionada (ej. estilo profesional para LinkedIn, conciso para X/Twitter, dinámico y con emojis/hashtags para Instagram).
    - Etiqueta claramente cada sección con el nombre de la red social (ej. ### Instagram, ### LinkedIn).
    """

    text_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=text_prompt
    )
    posts_text = text_response.text

    # 2. Generación de Imagen Conceptual con Gemini
    image_prompt = f"Una imagen promocional y profesional para redes sociales sobre la siguiente temática o marca: {source_input[:150]}"
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

    return posts_text, image_bytes
