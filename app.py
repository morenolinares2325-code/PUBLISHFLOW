import streamlit as st
from publisher import (
    generate_multi_platform_content, 
    analyze_product_and_generate_strategy,
    generate_weekly_calendar
)

st.set_page_config(page_title="PublishFlow AI Pro", page_icon="⚡", layout="wide")

# --- ESTILOS VISUALES MEJORADOS ---
st.markdown("""
    <style>
    .main-title { font-size: 2.4rem; font-weight: 800; color: #1E88E5; margin-bottom: 0px; }
    .sub-title { font-size: 1rem; color: #666; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; background-color: #f0f2f6; }
    .stTabs [aria-selected="true"] { background-color: #1E88E5 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ PublishFlow AI Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Suite inteligente para creación de contenido, estrategia comercial y planificación editorial.</p>', unsafe_allow_html=True)

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración Global")
language = st.sidebar.selectbox("🌐 Idioma:", ["Español", "Inglés", "Francés", "Alemán", "Portugués"])
tone = st.sidebar.selectbox("🎭 Tono de voz:", ["Profesional", "Cercano / Casual", "Persuasivo / Ventas", "Técnico / Experto", "Divertido"])
post_style = st.sidebar.selectbox("📐 Estilo del Post:", ["Estándar (Texto + Emojis)", "Hilo / Lista Educativa", "Enfoque Venta Directa (AIDA)"])
hashtag_count = st.sidebar.slider("🏷️ Límite de Hashtags:", min_value=0, max_value=30, value=10)

# --- PESTAÑAS DE NAVEGACIÓN ---
tab1, tab2, tab3 = st.tabs(["🤖 Contenido Multi-Red", "📸 Analizar Producto (A/B Test)", "📅 Calendario Editorial (7 Días)"])

# --- TAB 1: GENERADOR MULTI-RED ---
with tab1:
    col_in, col_opt = st.columns([2, 1])
    with col_in:
        source_input = st.text_area(
            "📝 Tema de origen o URL:", 
            placeholder="Ej: Estrategias de trading algorítmico o pega una URL...",
            height=120
        )
    with col_opt:
        selected_platforms = st.multiselect(
            "🎯 Redes Sociales Destino:",
            ["Instagram", "LinkedIn", "X (Twitter)", "Facebook"],
            default=["Instagram", "LinkedIn", "X (Twitter)"]
        )

    if st.button("🚀 Generar Publicaciones y Prompt de Imagen", type="primary", use_container_width=True):
        if not source_input:
            st.warning("⚠️ Introduce un tema o enlace de origen.")
        elif not selected_platforms:
            st.warning("⚠️ Selecciona al menos una red social.")
        else:
            with st.spinner("⏳ Generando copys optimizados y prompt de IA con Gemini..."):
                try:
                    result = generate_multi_platform_content(
                        source_input=source_input,
                        target_platforms=selected_platforms,
                        tone=tone,
                        language=language,
                        post_style=post_style,
                        hashtag_count=hashtag_count
                    )
                    st.success("✨ ¡Publicaciones generadas con éxito!")
                    st.markdown("---")
                    st.markdown(result)
                    
                    st.download_button(
                        label="📥 Descargar Publicaciones (.txt)",
                        data=result,
                        file_name="publicaciones_publishflow.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# --- TAB 2: ANÁLISIS DE PRODUCTO Y TEST A/B ---
with tab2:
    st.subheader("🔍 Análisis de Producto Real y Copys A/B")
    uploaded_file = st.file_uploader("Subir foto del producto (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    c1, c2 = st.columns(2)
    with c1:
        location = st.text_input("📍 Ubicación Objetivo:", "Madrid, España")
    with c2:
        audience = st.text_input("👥 Público Objetivo:", "Clientes interesados en el sector")

    if st.button("🚀 Analizar Producto y Generar Estrategia", type="primary", use_container_width=True):
        if not uploaded_file:
            st.warning("⚠️ Sube una foto de tu producto.")
        else:
            with st.spinner("🔍 Analizando imagen con Gemini Vision..."):
                try:
                    analysis = analyze_product_and_generate_strategy(
                        product_image_bytes=uploaded_file.getvalue(),
                        target_location=location,
                        target_audience=audience,
                        tone=tone,
                        language=language
                    )
                    st.success("✨ ¡Estrategia completada!")
                    st.markdown("---")
                    
                    col_img, col_txt = st.columns([1, 2])
                    with col_img:
                        st.image(uploaded_file.getvalue(), caption="Producto Analizado", use_container_width=True)
                    with col_txt:
                        st.markdown(analysis)
                        st.download_button(
                            label="📥 Descargar Estrategia (.txt)",
                            data=analysis,
                            file_name="estrategia_producto.txt",
                            mime="text/plain"
                        )
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# --- TAB 3: CALENDARIO EDITORIAL SEMANAL ---
with tab3:
    st.subheader("📅 Planificador Editorial de 7 Días")
    cal_input = st.text_input("💡 Introduce la temática central de la semana o una URL:", placeholder="Ej: Lanzamiento de nuevo curso de trading")

    if st.button("🗓️ Generar Calendario Semanal", type="primary", use_container_width=True):
        if not cal_input:
            st.warning("⚠️ Escribe una temática para planificar.")
        else:
            with st.spinner("⏳ Diseñando plan semanal de contenidos..."):
                try:
                    calendar_result = generate_weekly_calendar(
                        topic_or_url=cal_input,
                        language=language,
                        tone=tone
                    )
                    st.success("✨ ¡Calendario semanal listo!")
                    st.markdown("---")
                    st.markdown(calendar_result)
                    
                    st.download_button(
                        label="📥 Descargar Calendario (.txt)",
                        data=calendar_result,
                        file_name="calendario_semanal.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"❌ Error: {e}")
