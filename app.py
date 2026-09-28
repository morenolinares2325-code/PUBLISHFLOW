import streamlit as st
import os
from publisher import generate_multi_platform_content

st.set_page_config(page_title="PublishFlow AI", page_icon="⚡", layout="wide")

st.title("⚡ PublishFlow")
st.caption("Generador dinámico de publicaciones multired impulsado por Gemini API.")

# Configuración Lateral
st.sidebar.header("🔑 Configuración")
gemini_key = st.sidebar.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")

if gemini_key:
    os.environ["GEMINI_API_KEY"] = gemini_key

# Formulario Principal
st.subheader("1. Fuente de Información")
source_input = st.text_input(
    "Introduce la URL de tu sitio web / red social o el tema a publicitar:",
    placeholder="https://miweb.com o 'Lanzamiento de nuevo servicio de consultoría'"
)

st.subheader("2. Redes Sociales Destino")
selected_platforms = st.multiselect(
    "Selecciona las plataformas para las que deseas generar contenido:",
    ["Instagram", "LinkedIn", "X (Twitter)", "Facebook"],
    default=["Instagram", "LinkedIn"]
)

if st.button("🚀 Generar Publicaciones e Imagen", type="primary"):
    if not gemini_key:
        st.error("Introduce tu GEMINI_API_KEY en la barra lateral.")
    elif not source_input:
        st.warning("Introduce una URL o un tema de origen.")
    elif not selected_platforms:
        st.warning("Selecciona al menos una red social.")
    else:
        with st.spinner("PublishFlow analizando origen y generando contenido..."):
            try:
                posts_text, image_bytes = generate_multi_platform_content(
                    source_input, selected_platforms, api_key=gemini_key
                )
                st.session_state['posts_text'] = posts_text
                st.session_state['image_bytes'] = image_bytes
                st.success("¡Contenido generado con éxito!")
            except Exception as e:
                st.error(f"Error durante la generación: {e}")

# Resultados
if 'posts_text' in st.session_state:
    st.markdown("---")
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("📝 Copys Multired Generados")
        st.markdown(st.session_state['posts_text'])

    with col2:
        st.subheader("🖼️ Imagen Promocional IA")
        if st.session_state['image_bytes']:
            st.image(st.session_state['image_bytes'], use_container_width=True)
            st.download_button(
                label="⬇️ Descargar Imagen",
                data=st.session_state['image_bytes'],
                file_name="publishflow_post.png",
                mime="image/png"
            )
