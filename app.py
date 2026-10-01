import streamlit as st

st.set_page_config(
    page_title="PublishFlow",
    page_icon="🚀",
    layout="wide"
)

# ---------------------------------------------------
# ESTILOS
# ---------------------------------------------------

st.markdown("""
<style>

.stApp{
    background-color:#0B1020;
    color:white;
}

.hero{
    padding:40px;
    border-radius:20px;
    background:linear-gradient(135deg,#00E5FF,#8B5CF6);
    text-align:center;
    color:white;
}

.card{
    background:#131a2b;
    padding:20px;
    border-radius:20px;
    border:1px solid #2e3650;
    text-align:center;
}

.nombre{
    color:#00E5FF;
    font-size:22px;
    font-weight:bold;
}

.cargo{
    color:#8B5CF6;
    font-size:16px;
}

.estado{
    color:#00FFB3;
    font-size:14px;
    margin-top:10px;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# HERO
# ---------------------------------------------------

st.markdown("""
<div class="hero">
<h1>🚀 PublishFlow</h1>
<h3>Tu Departamento de Publicidad Digital</h3>

<p>
Sube tus imágenes, indica tus objetivos
y nuestro departamento preparará la campaña.
</p>

</div>
""", unsafe_allow_html=True)

st.write("")
st.write("")

# ---------------------------------------------------
# DEPARTAMENTO
# ---------------------------------------------------

st.subheader("🏢 Nuestro Departamento")

col1,col2,col3,col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="card">
    <h1>👨‍💼</h1>
    <div class="nombre">Javier Moreno Ruiz</div>
    <div class="cargo">Analista de Mercado</div>
    <div class="estado">🟢 Disponible</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="card">
    <h1>👩‍💼</h1>
    <div class="nombre">Laura Sánchez Martín</div>
    <div class="cargo">Planificadora Estratégica</div>
    <div class="estado">🟢 Disponible</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="card">
    <h1>👨‍💻</h1>
    <div class="nombre">Carlos Romero Ortega</div>
    <div class="cargo">Redactor Publicitario</div>
    <div class="estado">🟢 Disponible</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="card">
    <h1>👩‍💼</h1>
    <div class="nombre">Marta Fernández Delgado</div>
    <div class="cargo">Gestora de Difusión</div>
    <div class="estado">🟢 Disponible</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------
# FORMULARIO
# ---------------------------------------------------

st.subheader("📢 Nueva Campaña")

nombre = st.text_input("Nombre de la Campaña")

descripcion = st.text_area(
    "Describe tu producto o servicio"
)

objetivo = st.selectbox(
    "Objetivo",
    [
        "Conseguir Clientes",
        "Vender Productos",
        "Dar Visibilidad",
        "Generar Tráfico Web"
    ]
)

pais = st.text_input("País")

ciudad = st.text_input("Ciudad")

web = st.text_input("Sitio Web")

redes = st.multiselect(
    "Redes Sociales",
    [
        "Facebook",
        "Instagram",
        "LinkedIn",
        "Telegram"
    ]
)

imagenes = st.file_uploader(
    "Sube imágenes",
    accept_multiple_files=True,
    type=["jpg","png","jpeg","webp"]
)

modo = st.radio(
    "Modo de campaña",
    [
        "Publicar Ahora",
        "Programar",
        "Piloto Automático"
    ]
)

# ---------------------------------------------------
# BOTON
# ---------------------------------------------------

if st.button("🚀 Iniciar Campaña"):

    st.success("Campaña creada correctamente")

    st.markdown("### Estado del Departamento")

    st.info(
        "👨‍💼 Javier está analizando el mercado..."
    )

    st.info(
        "👩‍💼 Laura está diseñando la estrategia..."
    )

    st.info(
        "👨‍💻 Carlos está preparando publicaciones..."
    )

    st.info(
        "👩‍💼 Marta está organizando la difusión..."
    )

    st.progress(100)

    st.success(
        "Departamento listo para trabajar."
    )
