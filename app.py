import streamlit as st

# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

st.set_page_config(
    page_title="PublishFlow",
    page_icon="🚀",
    layout="wide"
)

# --------------------------------------------------
# CSS
# --------------------------------------------------

st.markdown("""
<style>

.stApp{
    background:#0B1020;
    color:white;
}

section[data-testid="stSidebar"]{
    background:#111827;
}

.hero{
    background:linear-gradient(135deg,#00E5FF,#8B5CF6);
    padding:35px;
    border-radius:20px;
    text-align:center;
    color:white;
    margin-bottom:20px;
}

.card{
    background:#131A2B;
    padding:20px;
    border-radius:15px;
    border:1px solid #1f2940;
    text-align:center;
    height:260px;
}

.agent-name{
    color:#00E5FF;
    font-size:20px;
    font-weight:bold;
}

.agent-role{
    color:#8B5CF6;
    font-size:15px;
}

.status{
    color:#00FFB3;
    font-weight:bold;
}

.metric{
    padding:15px;
    background:#131A2B;
    border-radius:15px;
    text-align:center;
}

.channel{
    background:#131A2B;
    padding:10px;
    border-radius:10px;
    margin-bottom:5px;
}

</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.title("🚀 PublishFlow")

    st.markdown("---")

    st.markdown("### 🏢 Departamento")

    st.markdown("""
✅ Javier Moreno Ruiz  
✅ Laura Sánchez Martín  
✅ Carlos Romero Ortega  
✅ Marta Fernández Delgado
    """)

    st.markdown("---")

    st.markdown("### 💰 Plan")

    st.success("5,99 €/mes")

# --------------------------------------------------
# HERO
# --------------------------------------------------

st.markdown("""
<div class="hero">

<h1>🚀 PublishFlow</h1>

<h3>Tu Departamento de Publicidad Digital</h3>

<p>
Analizamos tu negocio, diseñamos estrategias,
redactamos publicaciones y las difundimos
automáticamente en múltiples plataformas.
</p>

</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# METRICAS
# --------------------------------------------------

col1,col2,col3,col4 = st.columns(4)

with col1:
    st.metric("Especialistas", "4")

with col2:
    st.metric("Canales", "10")

with col3:
    st.metric("Plan", "5,99€")

with col4:
    st.metric("Estado", "Activo")

st.divider()

# --------------------------------------------------
# DEPARTAMENTO
# --------------------------------------------------

st.header("🏢 Departamento de Publicidad")

c1,c2,c3,c4 = st.columns(4)

with c1:
    st.markdown("""
    <div class="card">
    <h1>👨‍💼</h1>
    <div class="agent-name">
        Javier Moreno Ruiz
    </div>
    <div class="agent-role">
        Analista de Mercado
    </div>
    <br>
    Analiza sector, público,
    ubicación y canales.
    <br><br>
    <div class="status">
        🟢 Disponible
    </div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="card">
    <h1>👩‍💼</h1>
    <div class="agent-name">
        Laura Sánchez Martín
    </div>
    <div class="agent-role">
        Planificadora Estratégica
    </div>
    <br>
    Diseña campañas y
    calendarios.
    <br><br>
    <div class="status">
        🟢 Disponible
    </div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="card">
    <h1>👨‍💻</h1>
    <div class="agent-name">
        Carlos Romero Ortega
    </div>
    <div class="agent-role">
        Redactor Publicitario
    </div>
    <br>
    Redacta contenido para
    cada canal.
    <br><br>
    <div class="status">
        🟢 Disponible
    </div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div class="card">
    <h1>👩‍💼</h1>
    <div class="agent-name">
        Marta Fernández Delgado
    </div>
    <div class="agent-role">
        Gestora de Difusión
    </div>
    <br>
    Programa y supervisa
    publicaciones.
    <br><br>
    <div class="status">
        🟢 Disponible
    </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --------------------------------------------------
# CANALES
# --------------------------------------------------

st.header("🌐 Canales Compatibles")

col_a,col_b = st.columns(2)

with col_a:

    st.subheader("📱 Redes Sociales")

    st.markdown("""
✅ Facebook Pages

✅ Instagram Business

✅ LinkedIn Pages

✅ Telegram

✅ Threads
    """)

    st.subheader("📍 Negocio Local")

    st.markdown("""
✅ Google Business Profile
    """)

with col_b:

    st.subheader("📌 Descubrimiento")

    st.markdown("""
✅ Pinterest
    """)

    st.subheader("📰 Blogs y Publicación")

    st.markdown("""
✅ WordPress

✅ Medium

✅ Blogger
    """)

st.divider()

# --------------------------------------------------
# NUEVA CAMPAÑA
# --------------------------------------------------

st.header("📢 Crear Nueva Campaña")

nombre = st.text_input("Nombre de la Campaña")

descripcion = st.text_area(
    "Describe tu producto o servicio"
)

objetivo = st.selectbox(
    "Objetivo",
    [
        "Conseguir Clientes",
        "Vender Productos",
        "Captar Leads",
        "Generar Tráfico Web",
        "Aumentar Visibilidad",
        "Promoción Local",
        "Lanzamiento de Producto"
    ]
)

col1,col2 = st.columns(2)

with col1:
    pais = st.text_input("País")

with col2:
    ciudad = st.text_input("Ciudad")

sitio_web = st.text_input("Sitio Web")

canales = st.multiselect(
    "Canales Seleccionados",
    [
        "Facebook Pages",
        "Instagram Business",
        "LinkedIn Pages",
        "Telegram",
        "Google Business Profile",
        "Pinterest",
        "WordPress",
        "Medium",
        "Blogger",
        "Threads"
    ]
)

imagenes = st.file_uploader(
    "Subir imágenes",
    type=["jpg","jpeg","png","webp"],
    accept_multiple_files=True
)

modo = st.radio(
    "Modo de Publicación",
    [
        "Publicar Ahora",
        "Programar",
        "Piloto Automático"
    ]
)

# --------------------------------------------------
# EJECUCION
# --------------------------------------------------

if st.button("🚀 Iniciar Campaña", use_container_width=True):

    st.success("Campaña creada correctamente")

    st.subheader("📋 Estado del Departamento")

    st.info("👨‍💼 Javier está analizando el mercado...")
    st.info("👩‍💼 Laura está diseñando la estrategia...")
    st.info("👨‍💻 Carlos está redactando publicaciones...")
    st.info("👩‍💼 Marta está preparando la difusión...")

    st.progress(100)

    st.success("✅ Departamento operativo")

    st.markdown("""
### Resultado esperado

✅ Mercado analizado

✅ Estrategia definida

✅ Publicaciones adaptadas

✅ Canales seleccionados

✅ Campaña preparada
""")
