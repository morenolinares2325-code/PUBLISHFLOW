import streamlit as st

# =====================================================
# CONFIGURACION
# =====================================================

st.set_page_config(
    page_title="PublishFlow",
    page_icon="🚀",
    layout="wide"
)

# =====================================================
# ESTILOS
# =====================================================

st.markdown("""
<style>

.stApp{
    background:#0B1020;
    color:#FFFFFF;
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

.agent-card{
    background:#131A2B;
    border:1px solid #22304d;
    border-radius:18px;
    padding:20px;
    text-align:center;
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

.block{
    background:#131A2B;
    border-radius:15px;
    padding:15px;
    margin-bottom:10px;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("🚀 PublishFlow")

    st.success("Plan Profesional")

    st.markdown("---")

    st.subheader("🏢 Departamento")

    st.markdown("""
👨‍💼 **Javier Moreno Ruiz**  
*Analista de Mercado*

👩‍💼 **Laura Sánchez Martín**  
*Planificadora Estratégica*

👨‍💻 **Carlos Romero Ortega**  
*Redactor Publicitario*

👩‍💼 **Marta Fernández Delgado**  
*Gestora de Difusión*
""")

    st.markdown("---")

    st.subheader("🌐 Canales")

    st.markdown("""
✅ Facebook Pages

✅ Instagram Business

✅ LinkedIn Pages

✅ Telegram

✅ Google Business Profile

✅ Pinterest

✅ WordPress

✅ Medium

✅ Blogger

✅ Threads
""")

    st.markdown("---")

    st.success("Suscripción: 5,99 €/mes")

# =====================================================
# HERO
# =====================================================

st.markdown("""
<div class="hero">

<h1>🚀 PublishFlow</h1>

<h3>Tu Departamento de Publicidad Digital</h3>

<p>
Analizamos tu producto, diseñamos la estrategia,
preparamos las publicaciones y gestionamos
la difusión multicanal desde una única plataforma.
</p>

</div>
""", unsafe_allow_html=True)

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 Inicio",
    "📢 Campañas",
    "🏢 Departamento",
    "🌐 Canales",
    "📅 Calendario",
    "📊 Informes"
])

# =====================================================
# INICIO
# =====================================================

with tab1:

    st.header("🏠 Panel General")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Campañas", "0")
    c2.metric("Canales", "10")
    c3.metric("Especialistas", "4")
    c4.metric("Plan", "5.99€")

    st.divider()

    st.subheader("🎯 Objetivo de PublishFlow")

    st.info(
        "Sube tus imágenes, describe tu servicio y deja que "
        "nuestro Departamento de Publicidad prepare la campaña."
    )

# =====================================================
# CAMPAÑAS
# =====================================================

with tab2:

    st.header("📢 Nueva Campaña")

    nombre = st.text_input(
        "Nombre de la campaña"
    )

    descripcion = st.text_area(
        "Describe el producto o servicio"
    )

    objetivo = st.selectbox(
        "Objetivo principal",
        [
            "Conseguir Clientes",
            "Generar Leads",
            "Vender Productos",
            "Incrementar Visibilidad",
            "Promoción Local",
            "Tráfico Web",
            "Posicionamiento de Marca",
            "Evento",
            "Nueva Apertura",
            "Lanzamiento de Servicio"
        ]
    )

    col1, col2 = st.columns(2)

    with col1:
        pais = st.text_input("País")

    with col2:
        ciudad = st.text_input("Ciudad")

    sitio_web = st.text_input("Página web")

    st.subheader("🌐 Canales de Difusión")

    canales = st.multiselect(
        "",
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

    st.subheader("🖼️ Material Publicitario")

    imagenes = st.file_uploader(
        "Sube imágenes",
        accept_multiple_files=True,
        type=["jpg", "jpeg", "png", "webp"]
    )

    modo = st.radio(
        "Modo de publicación",
        [
            "Publicar Ahora",
            "Programar",
            "Piloto Automático"
        ]
    )

    st.divider()

    if st.button(
        "🚀 Activar Departamento",
        use_container_width=True
    ):

        st.success("Departamento activado correctamente")

        st.subheader("🏢 Proceso del Departamento")

        st.success(
            "✅ Javier está analizando tu sector y mercado."
        )

        st.success(
            "✅ Laura está diseñando la estrategia."
        )

        st.success(
            "✅ Carlos está redactando los contenidos."
        )

        st.success(
            "✅ Marta está preparando la difusión."
        )

        st.progress(100)

        st.divider()

        st.subheader(
            "📋 Informe Inicial"
        )

        st.info(f"""
Campaña: {nombre if nombre else 'Nueva campaña'}

Objetivo:
{objetivo}

País:
{pais}

Ciudad:
{ciudad}

Canales seleccionados:
{len(canales)}

Estado:
Lista para preparación.
""")

# =====================================================
# DEPARTAMENTO
# =====================================================

with tab3:

    st.header("🏢 Departamento de Publicidad")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.markdown("""
<div class="agent-card">
<h2>👨‍💼</h2>

<div class="agent-name">
Javier Moreno Ruiz
</div>

<div class="agent-role">
Analista de Mercado
</div>

<br>

Analiza:

• Sector

• Ubicación

• Público objetivo

• Canales recomendados

<br>

<div class="status">
🟢 Disponible
</div>
</div>
""", unsafe_allow_html=True)

    with a2:
        st.markdown("""
<div class="agent-card">
<h2>👩‍💼</h2>

<div class="agent-name">
Laura Sánchez Martín
</div>

<div class="agent-role">
Planificadora Estratégica
</div>

<br>

Define:

• Estrategia

• Frecuencia

• Calendario

• Objetivos

<br>

<div class="status">
🟢 Disponible
</div>
</div>
""", unsafe_allow_html=True)

    with a3:
        st.markdown("""
<div class="agent-card">
<h2>👨‍💻</h2>

<div class="agent-name">
Carlos Romero Ortega
</div>

<div class="agent-role">
Redactor Publicitario
</div>

<br>

Genera:

• Publicaciones

• Hashtags

• CTA

• Adaptaciones

<br>

<div class="status">
🟢 Disponible
</div>
</div>
""", unsafe_allow_html=True)

    with a4:
        st.markdown("""
<div class="agent-card">
<h2>👩‍💼</h2>

<div class="agent-name">
Marta Fernández Delgado
</div>

<div class="agent-role">
Gestora de Difusión
</div>

<br>

Gestiona:

• Programación

• Publicación

• Seguimiento

• Automatización

<br>

<div class="status">
🟢 Disponible
</div>
</div>
""", unsafe_allow_html=True)

# =====================================================
# CANALES
# =====================================================

with tab4:

    st.header("🌐 Canales Compatibles")

    st.success("✅ Facebook Pages")
    st.success("✅ Instagram Business")
    st.success("✅ LinkedIn Pages")
    st.success("✅ Telegram")
    st.success("✅ Google Business Profile")
    st.success("✅ Pinterest")
    st.success("✅ WordPress")
    st.success("✅ Medium")
    st.success("✅ Blogger")
    st.success("✅ Threads")

# =====================================================
# CALENDARIO
# =====================================================

with tab5:

    st.header("📅 Calendario")

    st.info("No existen publicaciones programadas.")

    st.markdown("""
**Ejemplo de automatización**

Lunes - Facebook

Martes - Instagram

Miércoles - LinkedIn

Jueves - Telegram

Viernes - Google Business
""")

# =====================================================
# INFORMES
# =====================================================

with tab6:

    st.header("📊 Informes")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Publicaciones",
        "0"
    )

    c2.metric(
        "Programadas",
        "0"
    )

    c3.metric(
        "Canales",
        "10"
    )

    st.divider()

    st.info(
        "Los informes de actividad aparecerán aquí cuando existan campañas activas."
    )
