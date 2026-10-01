import streamlit as st
import json
import os
from datetime import datetime

# =====================================================
# CONFIGURACION
# =====================================================

st.set_page_config(
    page_title="PublishFlow",
    page_icon="🚀",
    layout="wide"
)

# =====================================================
# BASE DE DATOS LOCAL
# =====================================================

DATA_FILE = "data/campanas.json"


def cargar_campanas():

    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def guardar_campana(campana):

    campanas = cargar_campanas()

    campanas.append(campana)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            campanas,
            f,
            ensure_ascii=False,
            indent=4
        )


# =====================================================
# ESTILOS
# =====================================================

st.markdown("""
<style>

.stApp{
    background:#0B1020;
}

section[data-testid="stSidebar"]{
    background:#111827;
}

.hero{
    padding:40px;
    border-radius:20px;
    background:linear-gradient(135deg,#00E5FF,#8B5CF6);
    color:white;
    text-align:center;
}

.agent-card{
    background:#131A2B;
    border-radius:20px;
    padding:20px;
    min-height:320px;
    border:1px solid #23304e;
}

.agent-name{
    color:#00E5FF;
    font-weight:bold;
    font-size:20px;
}

.agent-role{
    color:#8B5CF6;
}

.status{
    color:#00FFB3;
    font-weight:bold;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# DATOS
# =====================================================

campanas = cargar_campanas()

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("🚀 PublishFlow")

    st.success("Plan Profesional")

    st.markdown("---")

    st.markdown("""
### 🏢 Departamento

👨‍💼 Javier Moreno Ruiz

👩‍💼 Laura Sánchez Martín

👨‍💻 Carlos Romero Ortega

👩‍💼 Marta Fernández Delgado
""")

    st.markdown("---")

    st.markdown("""
### 🌐 Canales

✅ Facebook

✅ Instagram

✅ LinkedIn

✅ Telegram

✅ Google Business

✅ Pinterest

✅ WordPress

✅ Medium

✅ Blogger

✅ Threads
""")

    st.markdown("---")

    st.info("5,99 €/mes")

# =====================================================
# HERO
# =====================================================

st.markdown("""
<div class="hero">

<h1>🚀 PublishFlow</h1>

<h3>Tu Departamento de Publicidad Digital</h3>

<p>
Analizamos tu negocio, diseñamos estrategias,
redactamos publicaciones y organizamos
la difusión multicanal.
</p>

</div>
""", unsafe_allow_html=True)

st.write("")

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Inicio",
    "📢 Campañas",
    "🏢 Departamento",
    "🌐 Canales",
    "📅 Calendario",
    "📊 Informes",
    "📚 Historial"
])

# =====================================================
# INICIO
# =====================================================

with tab1:

    st.header("🏠 Panel General")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Campañas",
        len(campanas)
    )

    c2.metric(
        "Canales",
        "10"
    )

    c3.metric(
        "Especialistas",
        "4"
    )

    c4.metric(
        "Plan",
        "5.99 €"
    )

    st.divider()

    st.subheader("🎯 Objetivos disponibles")

    st.markdown("""
✅ Conseguir Clientes

✅ Captar Leads

✅ Vender Productos

✅ Incrementar Visibilidad

✅ Tráfico Web

✅ Posicionamiento de Marca

✅ Promoción Local

✅ Eventos

✅ Lanzamientos
""")

# =====================================================
# CAMPAÑAS
# =====================================================

with tab2:

    st.header("📢 Nueva Campaña")

    nombre = st.text_input(
        "Nombre de campaña"
    )

    descripcion = st.text_area(
        "Descripción"
    )

    objetivo = st.selectbox(
        "Objetivo",
        [
            "Conseguir Clientes",
            "Captar Leads",
            "Vender Productos",
            "Incrementar Visibilidad",
            "Promoción Local",
            "Tráfico Web",
            "Posicionamiento de Marca",
            "Evento",
            "Lanzamiento de Producto"
        ]
    )

    col1, col2 = st.columns(2)

    with col1:
        pais = st.text_input("País")

    with col2:
        ciudad = st.text_input("Ciudad")

    sitio_web = st.text_input("Sitio Web")

    canales = st.multiselect(
        "Selecciona Canales",
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
        "Material gráfico",
        accept_multiple_files=True
    )

    modo = st.radio(
        "Modo",
        [
            "Publicar Ahora",
            "Programar",
            "Piloto Automático"
        ]
    )

    if st.button(
        "🚀 Activar Departamento",
        use_container_width=True
    ):

        nueva = {
            "nombre": nombre,
            "descripcion": descripcion,
            "objetivo": objetivo,
            "pais": pais,
            "ciudad": ciudad,
            "web": sitio_web,
            "canales": canales,
            "fecha": datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
        }

        guardar_campana(nueva)

        st.success("Campaña registrada")

        st.write("")

        st.success(
            "✅ Javier ha comenzado el análisis del mercado"
        )

        st.success(
            "✅ Laura está preparando la estrategia"
        )

        st.success(
            "✅ Carlos está redactando publicaciones"
        )

        st.success(
            "✅ Marta está organizando la difusión"
        )

        st.progress(100)

# =====================================================
# DEPARTAMENTO
# =====================================================

with tab3:

    st.header("🏢 Departamento")

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

• Estudia sector

• Analiza ubicación

• Selecciona canales

• Identifica audiencia

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

• Diseña campañas

• Organiza calendario

• Define objetivos

• Planifica acciones

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

• Redacción

• Hashtags

• CTA

• Adaptación por canal

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

    dias = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes"
    ]

    publicaciones = [
        "Facebook",
        "Instagram",
        "LinkedIn",
        "Telegram",
        "Google Business"
    ]

    for dia, publicacion in zip(
        dias,
        publicaciones
    ):
        st.info(
            f"{dia} → {publicacion}"
        )

# =====================================================
# INFORMES
# =====================================================

with tab6:

    st.header("📊 Informes")

    total_campanas = len(campanas)

    total_canales = 0

    for campana in campanas:
        total_canales += len(
            campana.get(
                "canales",
                []
            )
        )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Campañas",
        total_campanas
    )

    c2.metric(
        "Canales Utilizados",
        total_canales
    )

    c3.metric(
        "Departamento",
        "Activo"
    )

# =====================================================
# HISTORIAL
# =====================================================

with tab7:

    st.header("📚 Historial")

    if not campanas:

        st.info(
            "Todavía no existen campañas."
        )

    else:

        for campana in reversed(campanas):

            with st.expander(
                campana["nombre"]
            ):

                st.write(
                    f"📅 {campana['fecha']}"
                )

                st.write(
                    f"🎯 {campana['objetivo']}"
                )

                st.write(
                    f"📍 {campana['pais']} - {campana['ciudad']}"
                )

                st.write(
                    campana["descripcion"]
                )

                st.write(
                    "🌐 Canales:"
                )

                for canal in campana["canales"\]:
                    st.write(
                        f"✅ {canal}"
                    )
