import streamlit as st
import pandas as pd

def render_buscador(get_gemini_client, modelos_validos):
    st.subheader("Buscador de Talentos y Creadores")
    st.write("Encuentra canales de YouTube, perfiles y creadores afines para acuerdos de afiliados o embajadores.")

    c1, c2, c3 = st.columns(3)
    with c1:
        nicho = st.text_input("Nicho / Palabra clave", value="Trading cuantitativo y algorithmic trading")
    with c2:
        tamano = st.selectbox("Audiencia aproximada", ["Micro (1K - 10K)", "Media (10K - 100K)", "Grande (100K+)"])
    with c3:
        idioma = st.selectbox("Idioma principal", ["Español", "Inglés", "Portugués"])

    if st.button("Buscar creadores con IA", type="primary"):
        client = get_gemini_client()
        with st.spinner("Javier Romero está analizando creadores potenciales..."):
            prompt = f"""
Eres Javier Romero Gil, Ojeador de Talento y Affiliates Manager.
Prospecciona 5 creadores/canales reales o perfiles arquetípicos muy detallados para el nicho: {nicho}.
Tamaño de audiencia: {tamano}
Idioma: {idioma}

Para cada creador proporciona en formato Markdown:
- Nombre / Handle del canal
- Plataforma principal
- Estimación de afinidad (Puntuación 1 a 10)
- Enfoque de su audiencia y por qué encaja
- Propuesta de primer mensaje personalizado (DM o Email) para invitarle a colaborar como afiliado
"""
            for modelo in modelos_validos:
                try:
                    resp = client.models.generate_content(model=modelo, contents=prompt)
                    st.markdown(resp.text)
                    break
                except Exception:
                    continue
            else:
                st.error("No se pudo conectar con el modelo para la prospección.")
