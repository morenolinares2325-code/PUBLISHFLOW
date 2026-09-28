import streamlit as st
from publisher import generate_multi_platform_content, analyze_product_and_generate_strategy

st.set_page_config(page_title="PublishFlow AI", page_icon="⚡", layout="wide")

st.title("⚡ PublishFlow")
st.caption("Motor de creación y estrategia de contenido impulsado por IA.")

# --- BARRA LATERAL: OPCIONES DE PUBLICACIÓN ---
st.sidebar.header("⚙️ Opciones de Publicación")

language = st.sidebar.selectbox("Idioma del contenido:", ["Español", "Inglés", "Francés", "Alemán", "Portugués"])
tone = st.sidebar.selectbox("Tono de voz:", ["Profesional", "Cercano / Casual", "Persuasivo / Ventas", "Técnico / Experto", "Divertido"])
post_style = st.sidebar.selectbox("Estilo del Post:", ["Estándar (Texto + Emojis)", "Hilo / Lista Educativa", "Enfoque Venta Directa (AIDA)"])
hashtag_count = st.sidebar.slider("Número de Hashtags:", min_value=0, max_value=30, value=10)

# --- SELECCIÓN DE MODO ---
modo = st.radio("Elige el tipo de trabajo:", ["🤖 Generar Contenido Multired (Texto / URL)", "📸 Analizar Producto Real (Modo Growth)"])

if modo == "🤖 Generar Contenido Multired (Texto / URL)":
    st.subheader("1. Origen del Contenido")
    source_input = st.text_input(
        "Introduce una URL o tema de origen:", 
        placeholder="Ej: https://miweb.com o 'Estrategias de trading algorítmico'"
    )
    
    st.subheader("2. Redes Sociales Destino")
    selected_platforms = st.multiselect(
        "Selecciona las redes para las que quieres crear contenido:",
        ["Instagram", "LinkedIn", "X (Twitter)", "Facebook"],
        default=["Instagram", "LinkedIn"]
    )

    if st.button("🚀 Generar Publicaciones", type="primary"):
        if not source_input:
            st.warning("Escribe un tema o introduce una URL.")
        elif not selected_platforms:
            st.warning("Selecciona al menos una red social.")
        else:
            with st.spinner("Generando publicaciones adaptadas con Gemini..."):
                try:
                    result = generate_multi_platform_content(
                        source_input=source_input,
                        target_platforms=selected_platforms,
                        tone=tone,
                        language=language,
                        post_style=post_style,
                        hashtag_count=hashtag_count
                    )
                    st.success("¡Contenido generado!")
                    st.markdown("---")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"❌ Error al generar: {e}")

else:
    st.subheader("Analizar Producto Real & Optimizar Alcance")
    uploaded_file = st.file_uploader("Subir foto de producto (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    col1, col2 = st.columns(2)
    with col1:
        location = st.text_input("Ubicación objetivo:", "Madrid, España")
    with col2:
        audience = st.text_input("Público Objetivo:", "Clientes interesados en el sector")

    if st.button("🚀 Analizar Producto y Generar Estrategia", type="primary"):
        if not uploaded_file:
            st.warning("Sube una foto de tu producto.")
        else:
            with st.spinner("Analizando la imagen del producto..."):
                try:
                    analysis = analyze_product_and_generate_strategy(
                        product_image_bytes=uploaded_file.getvalue(),
                        target_location=location,
                        target_audience=audience,
                        tone=tone,
                        language=language
                    )
                    st.success("¡Análisis completado!")
                    st.markdown("---")
                    
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(uploaded_file.getvalue(), caption="Producto", use_container_width=True)
                    with c2:
                        st.markdown(analysis)
                except Exception as e:
                    st.error(f"❌ Error: {e}")
