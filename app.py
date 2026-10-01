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
# BASE DE DATOS
# =====================================================

DATA_FILE = "data/campanas.json"

def cargar_campanas():

    if not os.path.exists(DATA_FILE):
        return []

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:
        return []


def guardar_campana(campana):

    campanas = cargar_campanas()

    campanas.append(campana)

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            campanas,
            f,
            ensure_ascii=False,
            indent=4
        )


campanas = cargar_campanas()

# =====================================================
# AGENTES
# =====================================================

def mostrar_agente(
    foto,
    nombre,
    cargo
):

    try:

        st.image(
            foto,
            use_container_width=True
        )

    except:

        st.warning(
            f"Falta imagen: {foto}"
        )

    st.markdown(
        f"### {nombre}"
    )

    st.caption(cargo)

# =====================================================
# ESTILOS
# =====================================================

st.markdown("""
<style>

/* =====================================================
FONDO GENERAL
===================================================== */

.stApp{

background:
radial-gradient(circle at top left,
rgba(255,0,128,.25),
transparent 30%),

radial-gradient(circle at top right,
rgba(180,0,255,.25),
transparent 35%),

radial-gradient(circle at bottom left,
rgba(255,0,255,.20),
transparent 40%),

radial-gradient(circle at bottom right,
rgba(120,0,255,.15),
transparent 40%),

#0f0820;

color:white;
}

/* =====================================================
SIDEBAR
===================================================== */

section[data-testid="stSidebar"]{

background:
linear-gradient(
180deg,
#14092A,
#231047,
#31155D
);
}

/* =====================================================
CABECERA
===================================================== */

.hero{

padding:45px;

border-radius:25px;

background:
linear-gradient(
135deg,
rgba(255,0,180,.18),
rgba(170,0,255,.18)
);

border:1px solid rgba(
255,
255,
255,
0.12
);

box-shadow:
0 0 15px rgba(
255,
0,
180,
0.12
);

color:white;

text-align:center;
}

/* =====================================================
TARJETAS
===================================================== */

.agent-card{

background:
rgba(
255,
255,
255,
0.06
);

backdrop-filter:blur(10px);

padding:20px;

border-radius:20px;

border:1px solid rgba(
255,
255,
255,
0.10
);

box-shadow:
0 0 10px rgba(
255,
0,
200,
0.08
);
}

/* =====================================================
TITULOS NEON SUAVE
===================================================== */

h1{

color:#FF4FD8 !important;

text-shadow:
0 0 4px rgba(255,79,216,0.45),
0 0 8px rgba(255,79,216,0.25);
}

h2{

color:#D39CFF !important;

text-shadow:
0 0 3px rgba(211,156,255,0.35);
}

h3{

color:#FF91EC !important;

text-shadow:
0 0 3px rgba(255,145,236,0.25);
}

/* =====================================================
TEXTOS
===================================================== */

p{
color:white !important;
}

label{
color:white !important;
font-weight:bold;
}

div{
color:white;
}

/* =====================================================
AGENTES
===================================================== */

.agent-name{

font-size:20px;

font-weight:bold;

color:#FF4FD8;

text-shadow:
0 0 3px rgba(255,79,216,0.30);
}

.agent-role{

font-size:15px;

color:#D39CFF;

text-shadow:
0 0 2px rgba(211,156,255,0.25);
}

.status{

color:#66FFC7;

font-weight:bold;

text-shadow:
0 0 2px rgba(102,255,199,0.20);
}

/* =====================================================
PESTAÑAS
===================================================== */

button[data-baseweb="tab"]{

color:white !important;

font-weight:bold;

font-size:15px;
}

button[data-baseweb="tab"][aria-selected="true"]{

color:#FF4FD8 !important;

text-shadow:
0 0 4px rgba(255,79,216,0.35);
}

/* =====================================================
INPUTS
===================================================== */

.stTextInput input{

background:
rgba(255,255,255,0.08) !important;

color:white !important;

border-radius:12px;

border:1px solid rgba(
255,
255,
255,
0.08
);
}

.stTextArea textarea{

background:
rgba(255,255,255,0.08) !important;

color:white !important;

border-radius:12px;

border:1px solid rgba(
255,
255,
255,
0.08
);
}

/* =====================================================
SELECTORES
===================================================== */
.stSelectbox *{
    color:white !important;
}

.stMultiSelect *{
    color:white !important;
}

/* =====================================================
BOTONES
===================================================== */

.stButton button{

background:
linear-gradient(
90deg,
#FF4FD8,
#B026FF
);

color:white;

font-weight:bold;

border:none;

border-radius:12px;

box-shadow:
0 0 8px rgba(
255,
79,
216,
0.25
);
}

/* =====================================================
METRICAS
===================================================== */

[data-testid="stMetric"]{

background:
rgba(
255,
255,
255,
0.05
);

padding:15px;

border-radius:15px;

border:1px solid rgba(
255,
255,
255,
0.08
);

box-shadow:
0 0 5px rgba(
255,
0,
200,
0.05
);
}

/* =====================================================
EXPANDERS
===================================================== */

.streamlit-expanderHeader{

color:#FF91EC !important;
}
/* =====================================================
TABS PREMIUM
===================================================== */

button[data-baseweb="tab"]{

    min-height:65px !important;

    min-width:190px !important;

    margin:8px !important;

    border-radius:18px !important;

    font-size:18px !important;

    font-weight:700 !important;

    color:white !important;

    background:
    rgba(255,255,255,0.08);

    border:
    1px solid rgba(255,255,255,0.10);
}

button[data-baseweb="tab"][aria-selected="true"]{

    background:
    linear-gradient(
        90deg,
        #FF4FD8,
        #B026FF
    ) !important;

    color:white !important;

    box-shadow:
    0 0 12px rgba(
        255,
        79,
        216,
        .25
    );
}
/* =====================================================
SELECTBOX Y MULTISELECT
===================================================== */

/* Caja cerrada */

.stSelectbox div[data-baseweb="select"]{
    background:rgba(255,255,255,0.08) !important;
    color:white !important;
    border-radius:12px !important;
}

.stMultiSelect div[data-baseweb="select"]{
    background:rgba(255,255,255,0.08) !important;
    color:white !important;
}

/* Texto seleccionado */

.stSelectbox span{
    color:white !important;
}

.stMultiSelect span{
    color:white !important;
}

/* Menú desplegable */

div[role="listbox"]{
    background:#1A1036 !important;
}

/* Opciones */

div[role="option"]{
    background:#1A1036 !important;
    color:white !important;
}

/* Opción al pasar el ratón */

div[role="option"\]:hover{
    background:#B026FF !important;
    color:white !important;
}

/* Texto del menú */

div[role="option"] span{
    color:white !important;
}
/* TEXTO SELECCIONADO EN SELECTBOX */

[data-baseweb="select"] span{
    color:#FFFFFF !important;
    font-weight:600 !important;
}

/* TEXTO DEL VALOR ELEGIDO */

[data-baseweb="select"] div{
    color:#FFFFFF !important;
}

/* MULTISELECT */

[data-baseweb="tag"]{
    background:#B026FF !important;
    color:white !important;
}

[data-baseweb="tag"] span{
    color:white !important;
}
</style>
""", unsafe_allow_html=True)
# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("🚀 PublishFlow")

    st.markdown("---")

    mostrar_agente(
        "assets/javier.jpg",
        "Javier Moreno Ruiz",
        "Analista de Mercado"
    )

    mostrar_agente(
        "assets/laura.jpg",
        "Laura Sánchez Martín",
        "Planificadora Estratégica"
    )

    mostrar_agente(
        "assets/carlos.jpg",
        "Carlos Romero Ortega",
        "Redactor Publicitario"
    )

    mostrar_agente(
        "assets/marta.jpg",
        "Marta Fernández Delgado",
        "Gestora de Difusión"
    )

    st.markdown("---")

    st.subheader(
        "🌐 Canales Compatibles"
    )

    st.markdown("""
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

# =====================================================
# CABECERA
# =====================================================

st.markdown("""

<div class="hero">

<h1>
🚀 PublishFlow
</h1>

<h3>
Tu Departamento de Publicidad Digital
</h3>

<p>

Sube imágenes.

Describe tu producto.

Nuestro equipo analizará,
planificará,
redactará
y gestionará la difusión.

</p>

</div>

""", unsafe_allow_html=True)

st.write("")
# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Inicio",
    "📢 Centro de Campañas",
    "🏢 Departamento",
    "🔗 Cuentas Conectadas",
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

    c1.metric("Campañas", len(campanas))
    c2.metric("Canales", "10")
    c3.metric("Especialistas", "4")
    c4.metric("Estado", "Operativo")

    st.divider()

    st.subheader("🏢 Departamento Activo")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        mostrar_agente(
            "assets/javier.jpg",
            "Javier Moreno Ruiz",
            "Analista de Mercado"
        )

    with a2:
        mostrar_agente(
            "assets/laura.jpg",
            "Laura Sánchez Martín",
            "Planificadora Estratégica"
        )

    with a3:
        mostrar_agente(
            "assets/carlos.jpg",
            "Carlos Romero Ortega",
            "Redactor Publicitario"
        )

    with a4:
        mostrar_agente(
            "assets/marta.jpg",
            "Marta Fernández Delgado",
            "Gestora de Difusión"
        )

# =====================================================
# CAMPAÑAS
# =====================================================
with tab2:

    st.header("📢 Centro de Campañas")

    nombre = st.text_input(
        "Nombre de la Campaña"
    )

    sector = st.selectbox(
        "Sector",
        [
            "Telecomunicaciones",
            "Tecnología",
            "Marketing",
            "Inmobiliaria",
            "Restauración",
            "Hostelería",
            "Salud",
            "Educación",
            "Turismo",
            "Ecommerce",
            "Servicios Profesionales",
            "Otro"
        ]
    )

    producto = st.text_input(
        "Producto o Servicio Principal"
    )

    descripcion = st.text_area(
        "Describe tu producto, servicio o negocio"
    )

    diferenciadores = st.text_area(
        "¿Por qué debería elegirte un cliente?"
    )

    publico = st.multiselect(
        "Público Objetivo",
        [
            "Particulares",
            "Autónomos",
            "Pymes",
            "Empresas",
            "Administraciones Públicas"
        ]
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        pais = st.text_input("País")

    with col2:
        provincia = st.text_input("Provincia")

    with col3:
        ciudad = st.text_input("Ciudad")

    objetivo = st.selectbox(
        "Objetivo Principal",
        [
            
        "Conseguir Suscriptores",   
        "Conseguir Clientes",
        "Captar Leads",
        "Generar Llamadas",
        "Solicitar Presupuestos",
        "Vender Productos",
        "Promocionar Servicios",
        "Aumentar Visibilidad",
        "Posicionamiento de Marca",
        "Aumentar Tráfico Web",
        "Promoción Local",
        "Promocionar Evento",
        "Lanzamiento de Producto"
    ]
)
        ]
    )

    prioridad = st.select_slider(
        "Prioridad",
        [
            "Baja",
            "Media",
            "Alta",
            "Crítica"
        ]
    )

    canales = st.multiselect(
        "Canales de Difusión",
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
        "📁 Material de Campaña",
        accept_multiple_files=True
    )

    if st.button(
        "🚀 Activar Departamento",
        use_container_width=True
    ):

        nueva = {

            "nombre": nombre,

            "sector": sector,

            "producto": producto,

            "descripcion": descripcion,

            "diferenciadores": diferenciadores,

            "publico": publico,

            "pais": pais,

            "provincia": provincia,

            "ciudad": ciudad,

            "objetivo": objetivo,

            "prioridad": prioridad,

            "canales": canales,

            "fecha": datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
        }

        guardar_campana(nueva)

        st.success(
            "✅ Campaña registrada correctamente"
        )

        st.progress(25)
        st.info(
            "🔍 Javier analizando mercado y competencia"
        )

        st.progress(50)
        st.info(
            "📋 Laura construyendo estrategia"
        )

        st.progress(75)
        st.info(
            "✍️ Carlos preparando contenidos"
        )

        st.progress(100)
        st.info(
            "📢 Marta organizando difusión"
        )
# =====================================================
# DEPARTAMENTO
# =====================================================

with tab3:

    st.header(
        "🏢 Departamento de Publicidad"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        mostrar_agente(
            "assets/javier.jpg",
            "Javier Moreno Ruiz",
            "Analista de Mercado"
        )

        st.write("""
• Estudio de mercado

• Público objetivo

• Selección de canales

• Investigación geográfica
""")

    with c2:

        mostrar_agente(
            "assets/laura.jpg",
            "Laura Sánchez Martín",
            "Planificadora Estratégica"
        )

        st.write("""
• Estrategia

• Calendario

• Organización

• Objetivos
""")

    with c3:

        mostrar_agente(
            "assets/carlos.jpg",
            "Carlos Romero Ortega",
            "Redactor Publicitario"
        )

        st.write("""
• Publicaciones

• CTA

• Hashtags

• Adaptación por plataforma
""")

    with c4:

        mostrar_agente(
            "assets/marta.jpg",
            "Marta Fernández Delgado",
            "Gestora de Difusión"
        )

        st.write("""
• Programación

• Difusión

• Seguimiento

• Automatización
""")

# =====================================================
# CANALES
# =====================================================
with tab4:

    st.header(
        "🔗 Cuentas Conectadas"
    )

    st.info(
        "Aquí aparecerán las cuentas del cliente conectadas a PublishFlow."
    )

    st.success("Facebook")
    st.success("Instagram")
    st.success("LinkedIn")
    st.success("Telegram")
    st.success("Google Business")
    st.success("Pinterest")
    st.success("WordPress")
    st.success("Medium")
    st.success("Blogger")
    st.success("Threads")

    st.caption(
        "Próximamente podrás autorizar cada cuenta para publicar automáticamente."
    )
# =====================================================
# CALENDARIO
# =====================================================

with tab5:

    st.header("📅 Calendario")

    calendario = {
        "Lunes":"Facebook",
        "Martes":"Instagram",
        "Miércoles":"LinkedIn",
        "Jueves":"Telegram",
        "Viernes":"Google Business",
        "Sábado":"Pinterest",
        "Domingo":"WordPress"
    }

    for dia, canal in calendario.items():

        st.info(
            f"{dia} → {canal}"
        )

# =====================================================
# INFORMES
# =====================================================

with tab6:

    st.header("📊 Informes")

    total = len(campanas)

    total_canales = 0

    for c in campanas:
        total_canales += len(
            c.get(
                "canales",
                []
            )
        )

    a, b, c = st.columns(3)

    a.metric(
        "Campañas",
        total
    )

    b.metric(
        "Canales Utilizados",
        total_canales
    )

    c.metric(
        "Departamento",
        "Activo"
    )

# =====================================================
# HISTORIAL
# =====================================================

# =====================================================
# HISTORIAL
# =====================================================

with tab7:

    st.header(
        "📚 Historial de Campañas"
    )

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
                    "🌐 Canales seleccionados:"
                )

                for canal in campana["canales"]:

                    st.write(
                        f"✅ {canal}"
                    )
