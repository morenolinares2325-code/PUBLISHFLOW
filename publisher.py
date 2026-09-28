import os
from PIL import Image
from google import genai

def analyze_product_and_generate_strategy(product_image_bytes, target_location: str, target_audience: str, api_key: str = None):
    """
    Analiza una imagen real del producto mediante Gemini Vision 
    y genera copys, ubicación sugerida, hashtags y horarios picos.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=key)

    # Convertir bytes a objeto PIL para Gemini
    import io
    image = Image.open(io.BytesIO(product_image_bytes))

    prompt = f"""
    Eres un experto en Growth Hacking y Social Media Marketing.
    
    Analiza detalladamente la imagen adjunta de este producto.
    - Ubicación / Mercado Objetivo: {target_location}
    - Púbico Objetivo: {target_audience}

    Genera una estrategia completa para Instagram/Facebook con los siguientes apartados etiquetados:
    
    ### 📝 Copy Comercial
    (Un texto persuasivo utilizando el modelo AIDA: Atención, Interés, Deseo, Acción, con emojis).

    ### 📍 Ubicación Estratégica Sugerida
    (Sugiere 3 ubicaciones de Instagram específicas en {target_location} para etiquetar la foto y maximizar el alcance local).

    ### ⏰ Mejor Día y Horario de Publicación
    (Indica los 2 mejores momentos de la semana para publicar este producto según el target).

    ### 🏷️ Hashtags de Alto Impacto
    (Lista de 15-20 hashtags divididos entre gran alcance, nicho y locales).

    ### 👁️ Texto Alternativo (SEO para Algoritmos)
    (Una descripción técnica corta para el Alt-Text de Instagram).
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image, prompt]
    )

    return response.text
