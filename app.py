import streamlit as st
import os
from publisher import analyze_product_and_generate_strategy, generate_multi_platform_content

st.set_page_config(page_title="PublishFlow AI — Product Growth", page_icon="⚡", layout="wide")

st.title("⚡ PublishFlow — Content & Product Engine")

st.sidebar.header("🔑 Configuración")
gemini_key = st.sidebar.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")

if gemini_key:
    os.environ["GEMINI_API_KEY"] = gemini_key

# Selector de Modo
modo = st.radio("Elige el tipo de publicación:", ["📸 Foto Real de Producto (Modo Growth)", "🤖 Generación 100% IA (Texto e Imagen)"])

if modo == "📸 Foto Real de Producto (Modo Growth)":
    st.subheader("Subir Producto Real & Optimizar Alcance")
    
    uploaded_file = st.file_uploader("Subir imagen de tu producto (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    col_a, col_b = st.columns(2)
    with col_a:
        location = st.text_input("Ubicación objetivo (Ciudad/País):", "Madrid, España")
    with col_b:
        audience = st.text_input("Público Objetivo:", "Jóvenes profesionales de 25-40 años interesados en tecnología")

    if st.button("🚀 Analizar Producto y Generar Publicación Óptima", type="primary"):
        if not gemini_key:
            st.error("Por favor ingresa tu GEMINI_API_KEY.")
        elif not uploaded_file:
            st.warning("Sube una foto de tu producto.")
        else:
            with st.spinner("Gemini analizando la foto de tu producto y calculando la mejor estrategia..."):
                try:
                    img_bytes = uploaded_file.getvalue()
                    analysis_result = analyze_product_and_generate_strategy(img_bytes, location, audience, api_key=gemini_key)
                    
                    st.success("¡Estrategia y contenido listos!")
                    
                    col1, col2 = st.columns([2, 3])
                    with col1:
                        st.image(img_bytes, caption="Producto Subido", use_container_width=True)
                    with col2:
                        st.markdown(analysis_result)
                        
                except Exception as e:
                    st.error(f"Error procesando la imagen: {e}")

else:
    # Mantenemos el flujo previo de generación 100% IA
    st.subheader("Generación de Contenido e Imagen con IA")
    source_input = st.text_input("Tema o URL de la web:")
    if st.button("Generar Todo con IA"):
        st.info("Utilizando el generador automático de imágenes y texto.")
