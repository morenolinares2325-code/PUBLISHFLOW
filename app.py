import os
import time
import requests
from PIL import Image
import io
from bs4 import BeautifulSoup
import streamlit as st
from google import genai
from google.genai.errors import APIError

# Configuración de la página de Streamlit
st.set_page_config(
    page_title="Gestor de Redes Sociales con IA",
    page_icon="🚀",
    layout="wide"
)

# Únicamente modelos vigentes permitidos por la API actual
MODELOS_VALIDOS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash"
]

def get_gemini_client():
    """Obtiene el cliente del SDK oficial google-genai desde los Secrets o variables de entorno."""
    key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if isinstance(key, str):
        key = key.strip().strip('"').strip("'")
    
    if not key:
        st.error("🔑 **Error de Clave API:** No se encontró `GEMINI_API_KEY` en los Secrets de Streamlit.")
        st.stop()
    
    return genai.Client(api_key=key)

def call_gemini_with_fallback_and_retry(client, contents, retries_per_model=3):
    """
    Intenta ejecutar la petición probando en orden los modelos válidos actuales.
    Si recibe un 404 (modelo no disponible o nombre antiguo), pasa inmediatamente al siguiente.
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
                # Si el modelo no existe o da 404/400, saltar de inmediato al siguiente modelo
                if getattr(e, 'code', None) in [404, 400] or "NOT_FOUND" in err_str or "INVALID_ARGUMENT" in err_str:
                    break
                # Para saturación (503) o cuota (429), reintentar esperando
                time.sleep((attempt + 1) * 2)
            except Exception as e:
                last_error = e
                time.sleep((attempt + 1) * 2)

    if last_error:
        raise last_error
    else:
        raise RuntimeError("No se pudo obtener respuesta de ningún modelo de Gemini.")

def fetch_url_content(url: str) -> str:
    """Extrae texto principal de una URL dada."""
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

def generate_multi_platform_content(source_input: str, target_platforms: list, tone: str, language: str, post_style: str, hashtag_count: int):
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

def analyze_product_and_generate_strategy(product_image_bytes, target_location: str, target_audience: str, tone: str, language: str):
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

def generate_weekly_calendar(topic_or_url: str, language: str, tone: str):
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

def generate_video_script(topic: str, video_duration: str, language: str, tone: str):
    """NUEVA FUNCIÓN: Genera un guion técnico y narrativo para vídeos cortos (Reels, TikTok, Shorts)."""
    client = get_gemini_client()

    prompt = f"""
    Eres un creador de contenido viral y director audiovisual para redes sociales.
    Crea un guion detallado para un vídeo vertical corto (Reels / TikTok / YouTube Shorts).

    TEMA/CONCEPTO: "{topic}"
    DURACIÓN ESTIMADA: {video_duration}
    IDIOMA: {language}
    TONO DE VOZ: {tone}

    ESTRUCTURA REQUERIDA:
    ### 🎣 Gancho Visual y Vocal (Primeros 3 Segundos)
    - **Texto en Pantalla (Hook):**
    - **Lo que dice la voz en off/presentador:**
    - **Acción / Plano de Cámara:**

    ### 🎬 Desarrollo del Vídeo (Paso a Paso)
    Organiza el guion en una tabla o lista indicando:
    1. **Tiempo (Segundos):**
    2. **Audio / Locución:**
    3. **Visual / B-Roll / Efecto en Pantalla:**

    ### 🎯 Llamada a la Acción (CTA Final)
    - Frase de cierre persuasiva para fomentar comentarios o guardados.

    ### 🎵 Sugerencia de Audio / Música de Fondo
    - Estilo de música o efecto sonoro recomendado.
    """

    response = call_gemini_with_fallback_and_retry(client, prompt)
    return response.text


# -------------------------------------------------------------------
# INTERFAZ STREAMLIT
# -------------------------------------------------------------------

st.title("🚀 Creador y Estratega de Contenido para Redes Sociales")
st.write("Genera publicaciones multicanal, analiza imágenes, planifica calendarios o diseña guiones de vídeo con IA.")

# Configuración en la barra lateral
with st.sidebar:
    st.header("⚙️ Configuración")
    language = st.selectbox("Idioma", ["Español", "Inglés", "Portugués", "Francés", "Alemán"])
    tone = st.selectbox("Tono de voz", ["Profesional", "Cercano / Amigable", "Persuasivo", "Educativo", "Humorístico", "Urgente / Directo"])
    post_style = st.selectbox("Estilo del post", ["Estándar", "Storytelling", "Puntos clave / Listado", "Minimalista", "Pregunta para interactuar"])
    hashtag_count = st.slider("Número de hashtags", min_value=0, max_value=30, value=10)

tabs = st.tabs([
    "📲 Generador Multi-Redes", 
    "📸 Análisis de Producto / Vehículo", 
    "📅 Calendario Semanal",
    "🎥 Guion para Reels / TikTok"
])

# PESTAÑA 1: GENERADOR MULTI-REDES
with tabs[0]:
    st.subheader("Generar contenido para múltiples redes")
    source_input = st.text_area("Ingresa una idea, texto base o una URL para extraer el contenido:", height=100)
    
    target_platforms = st.multiselect(
        "Selecciona las redes sociales objetivo:",
        ["Instagram", "LinkedIn", "X (Twitter)", "Facebook", "TikTok / Reels", "Threads"],
        default=["Instagram", "LinkedIn", "X (Twitter)"]
    )

    if st.button("🚀 Generar Publicaciones", type="primary", key="btn_multi"):
        if not source_input.strip():
            st.warning("Por favor, introduce un texto o URL.")
        elif not target_platforms:
            st.warning("Selecciona al menos una red social.")
        else:
            with st.spinner("Procesando contenido con Gemini..."):
                try:
                    resultado = generate_multi_platform_content(
                        source_input=source_input,
                        target_platforms=target_platforms,
                        tone=tone,
                        language=language,
                        post_style=post_style,
                        hashtag_count=hashtag_count
                    )
                    st.success("¡Contenido generado exitosamente!")
                    st.markdown(resultado)
                except Exception as e:
                    st.error(f"Error al generar el contenido: {e}")

# PESTAÑA 2: ANÁLISIS DE PRODUCTO / VEHÍCULO
with tabs[1]:
    st.subheader("Estrategia visual a partir de una imagen")
    uploaded_file = st.file_uploader("Sube una imagen de tu producto o vehículo:", type=["jpg", "jpeg", "png", "webp"])
    
    col1, col2 = st.columns(2)
    with col1:
        target_location = st.text_input("Ubicación objetivo (ej. Madrid, España / Bogotá / Online):", value="Madrid, España")
    with col2:
        target_audience = st.text_input("Público objetivo (ej. Jóvenes profesionales, Familias):", value="Público general")

    if uploaded_file is not None:
        # Parámetro actualizado para evitar TypeError en versiones recientes de Streamlit
        st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Analizar Imagen y Generar Estrategia", type="primary", key="btn_img"):
        if uploaded_file is None:
            st.warning("Por favor, sube una imagen primero.")
        else:
            with st.spinner("Analizando la imagen con IA..."):
                try:
                    img_bytes = uploaded_file.getvalue()
                    resultado = analyze_product_and_generate_strategy(
                        product_image_bytes=img_bytes,
                        target_location=target_location,
                        target_audience=target_audience,
                        tone=tone,
                        language=language
                    )
                    st.success("¡Análisis y estrategia completados!")
                    st.markdown(resultado)
                except Exception as e:
                    st.error(f"Error al analizar la imagen: {e}")

# PESTAÑA 3: CALENDARIO SEMANAL
with tabs[2]:
    st.subheader("Planificación de contenidos para 7 días")
    calendar_input = st.text_area("Describe el tema, nicho o URL sobre la que deseas el plan semanal:", height=100)

    if st.button("📅 Crear Plan Semanal", type="primary", key="btn_cal"):
        if not calendar_input.strip():
            st.warning("Por favor, introduce el tema o URL para el calendario.")
        else:
            with st.spinner("Creando calendario de 7 días..."):
                try:
                    resultado = generate_weekly_calendar(
                        topic_or_url=calendar_input,
                        language=language,
                        tone=tone
                    )
                    st.success("¡Calendario generado exitosamente!")
                    st.markdown(resultado)
                except Exception as e:
                    st.error(f"Error al crear el calendario: {e}")

# PESTAÑA 4: GUION PARA VÍDEOS CORTOS (REELS / TIKTOK)
with tabs[3]:
    st.subheader("🎥 Generador de Guiones para Reels, TikTok y YouTube Shorts")
    video_topic = st.text_area("¿De qué trata tu vídeo? (Ej. 3 trucos para mejorar tu CV, Presentación de nuevo coche):", height=100)
    
    video_duration = st.selectbox("Duración estimada del vídeo:", ["15 segundos (Formato ultra rápido)", "30 segundos (Recomendado)", "60 segundos (Explicativo)"])

    if st.button("🎬 Generar Guion de Vídeo", type="primary", key="btn_script"):
        if not video_topic.strip():
            st.warning("Por favor, describe el concepto o tema del vídeo.")
        else:
            with st.spinner("Diseñando el guion gráfico y la locución..."):
                try:
                    resultado = generate_video_script(
                        topic=video_topic,
                        video_duration=video_duration,
                        language=language,
                        tone=tone
                    )
                    st.success("¡Guion listo para grabar!")
                    st.markdown(resultado)
                except Exception as e:
                    st.error(f"Error al generar el guion: {e}")
