import os
import base64
import datetime as dt

import pandas as pd
import streamlit as st
from google import genai

import motor
from buscador_colaboradores import render_buscador

st.set_page_config(page_title="PublishFlow Agencia", page_icon="📣", layout="wide")

MODELOS_VALIDOS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
]


# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
def leer_secretos():
    try:
        return {k: v for k, v in st.secrets.items()}
    except Exception:
        return {}


SECRETOS = leer_secretos()


def get_gemini_client():
    key = SECRETOS.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    key = str(key).strip().strip('"').strip("'")
    if not key:
        st.error("🔑 Falta `GEMINI_API_KEY` en los Secrets de Streamlit.")
        st.stop()
    return genai.Client(api_key=key)


st.session_state.setdefault("campana", None)
st.session_state.setdefault("registro", [])

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap');
html, body, .stMarkdown, .stButton button, h1, h2, h3 { font-family: 'Manrope', system-ui, sans-serif; }
.miembro { border: 1px solid #D7DDE8; border-radius: 16px; padding: 18px 14px; text-align: center;
           background: #FFFFFF; margin-bottom: 14px; }
.miembro img { width: 104px; height: 104px; border-radius: 50%; object-fit: cover;
               background: #E9EDF5; border: 3px solid #FFFFFF; box-shadow: 0 0 0 2px #D7DDE8; }
.miembro .nombre { font-weight: 800; font-size: 1.05rem; margin-top: 10px; color: #172033; }
.miembro .rol { color: #46556F; font-size: .92rem; }
.miembro .bio { color: #66748C; font-size: .84rem; margin-top: 6px; line-height: 1.35; }
.miembro .estado { margin-top: 10px; font-size: .82rem; font-weight: 600; color: #15803D; }
.miembro .estado.libre { color: #8A94A6; font-weight: 400; }
.firma { display: flex; align-items: center; gap: 12px; margin: 4px 0 12px; }
.firma img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; background: #E9EDF5; }
.firma b { color: #172033; } .firma span { color: #46556F; font-size: .9rem; }
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------------
# EQUIPO: fotos y tarjetas
# -------------------------------------------------------------------
@st.cache_data
def foto_src(id_miembro, nombre):
    """Usa fotos/<id>.jpg|png si existe; si no, un avatar ilustrado."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        ruta = os.path.join("fotos", f"{id_miembro}.{ext}")
        if os.path.exists(ruta):
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            with open(ruta, "rb") as f:
                return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    semilla = nombre.replace(" ", "%20")
    return f"https://api.dicebear.com/9.x/notionists/png?seed={semilla}&backgroundColor=e9edf5"


def firma(id_miembro):
    m = motor.EQ[id_miembro]
    st.markdown(
        f'<div class="firma"><img src="{foto_src(m["id"], m["nombre"])}">'
        f'<div><b>{m["nombre"]}</b><br><span>{m["rol"]}</span></div></div>',
        unsafe_allow_html=True,
    )


def estado_miembro(id_miembro):
    camp = st.session_state.campana
    if not camp:
        return "Disponible", True
    n = len(camp["redes"])
    publicadas = sum(1 for r in st.session_state.registro if r["campaña"] == camp["id"])
    estados = {
        "estrategia": "Plan de campaña entregado",
        "copy": f"{n} textos entregados",
        "creativa": f"{n} piezas y guion entregados",
        "community": f"{publicadas} de {n} publicaciones hechas",
        "analista": "Siguiendo resultados" if publicadas else "Esperando las primeras publicaciones",
        "talento": "Disponible para buscar colaboradores",
    }
    return estados[id_miembro], id_miembro == "talento"


def tarjeta(m):
    estado, libre = estado_miembro(m["id"])
    clase = "estado libre" if libre else "estado"
    return (f'<div class="miembro"><img src="{foto_src(m["id"], m["nombre"])}">'
            f'<div class="nombre">{m["nombre"]}</div><div class="rol">{m["rol"]}</div>'
            f'<div class="bio">{m["bio"]}</div><div class="{clase}">● {estado}</div></div>')


# -------------------------------------------------------------------
# CAMPAÑA
# -------------------------------------------------------------------
def ejecutar_campana(brief, fotos, logo, color, redes, idioma, tono):
    client = get_gemini_client()
    eq = motor.EQ
    with st.status("El equipo está trabajando en tu campaña…", expanded=True) as estado:
        st.write(f"🧭 {eq['estrategia']['nombre']} está analizando mercados, público y horarios…")
        estrategia = motor.crear_estrategia(client, MODELOS_VALIDOS, brief, redes, idioma, fotos)

        st.write(f"✍️ {eq['copy']['nombre']} está escribiendo las publicaciones…")
        copy = motor.escribir_publicaciones(client, MODELOS_VALIDOS, brief, estrategia,
                                            redes, idioma, tono)

        st.write(f"🎨 {eq['creativa']['nombre']} está preparando las piezas visuales y el guion…")
        gancho = copy.get("gancho_imagen", "")
        piezas = {}
        for i, red in enumerate(redes):
            foto = fotos[i % len(fotos)] if fotos else None
            piezas[red] = motor.crear_pieza(foto, motor.REDES[red]["tamano"], color, gancho, logo)
        guion = motor.escribir_guion(client, MODELOS_VALIDOS, brief, estrategia, idioma, tono)

        st.write(f"📅 {eq['community']['nombre']} está organizando la publicación…")
        publicaciones = copy.get("publicaciones", {})
        for red in redes:
            publicaciones.setdefault(red, {"texto": "", "variante_b": "", "hashtags": []})

        estado.update(label="Campaña lista. Revisa las entregas del equipo.",
                      state="complete", expanded=False)

    ahora = dt.datetime.now()
    return {
        "id": ahora.strftime("%Y%m%d%H%M%S"),
        "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
        "brief": brief,
        "marca": brief["marca"],
        "nombre": f"{brief['marca']} {ahora.strftime('%d-%m')}",
        "redes": redes,
        "estrategia": estrategia,
        "gancho": gancho,
        "publicaciones": publicaciones,
        "piezas": piezas,
        "guion": guion,
    }


def textos_campana(camp):
    return {red: motor.texto_final(camp["publicaciones"][red],
                                   motor.enlace_utm(camp["brief"]["url"], red, camp["nombre"]),
                                   red)
            for red in camp["redes"]}


def horarios(camp):
    return {r.get("red"): ", ".join(r.get("horarios", []))
            for r in camp["estrategia"].get("redes", []) if isinstance(r, dict)}


def tabla(datos):
    if isinstance(datos, list) and datos:
        st.dataframe(pd.DataFrame(datos), hide_index=True)


# -------------------------------------------------------------------
# BARRA LATERAL
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Ajustes de la agencia")
    idioma = st.selectbox("Idioma de las publicaciones",
                          ["Español", "Inglés", "Portugués", "Francés", "Alemán"])
    tono = st.selectbox("Tono de voz",
                        ["Cercano / Amigable", "Profesional", "Persuasivo", "Educativo",
                         "Humorístico", "Urgente / Directo"])
    st.divider()
    st.subheader("Redes conectadas")
    for red in motor.SECRETS_RED:
        st.write(("🟢 " if motor.conectado(red, SECRETOS) else "⚪ ") + red)
    st.caption("Las redes se conectan añadiendo sus claves en los Secrets de Streamlit. "
               "El resto se descarga para subirlo a mano.")

tab_oficina, tab_encargo, tab_entregas, tab_publicar, tab_resultados, tab_talento = st.tabs(
    ["🏢 Oficina", "📋 Nuevo encargo", "📦 Entregas", "📤 Publicación", "📈 Resultados", "🤝 Talento"]
)

# -------------------------------------------------------------------
# OFICINA
# -------------------------------------------------------------------
with tab_oficina:
    st.title("Tu agencia de marketing")
    st.write("Seis especialistas para tus marcas. Encarga una campaña y cada uno te entrega su parte.")
    columnas = st.columns(3)
    for i, m in enumerate(motor.EQUIPO):
        with columnas[i % 3]:
            st.markdown(tarjeta(m), unsafe_allow_html=True)

    camp = st.session_state.campana
    if camp:
        st.subheader(f"Campaña en curso: {camp['marca']}")
        st.write(camp["estrategia"].get("resumen", ""))
        st.caption(f"Encargada el {camp['fecha']}. Revisa el trabajo en la pestaña Entregas.")
    else:
        st.info("No hay ninguna campaña en marcha. Ve a «Nuevo encargo» y pásale el briefing al equipo.")

# -------------------------------------------------------------------
# NUEVO ENCARGO
# -------------------------------------------------------------------
with tab_encargo:
    st.subheader("Briefing para el equipo")
    c1, c2 = st.columns(2)
    with c1:
        marca = st.selectbox("Marca", list(motor.MARCAS))
        datos_marca = motor.MARCAS[marca]
        descripcion = st.text_area("Qué quieres promocionar", value=datos_marca["descripcion"],
                                   height=120, key=f"desc_{marca}")
        url = st.text_input("Enlace de destino", value=datos_marca["url"], key=f"url_{marca}")
        objetivo = st.selectbox("Objetivo", ["Conseguir suscriptores de pago", "Visitas a la web",
                                             "Seguidores en redes", "Lanzar una novedad",
                                             "Promoción u oferta"])
        oferta = st.text_input("Oferta o llamada a la acción (opcional)",
                               placeholder="Ej.: precio fundador para los 100 primeros")
    with c2:
        mercado = st.text_input("Mercado o país", value="España")
        publico = st.text_input("Público (opcional, si no lo decide Elena)")
        fotos_subidas = st.file_uploader("Fotos o capturas del producto",
                                         type=["jpg", "jpeg", "png", "webp"],
                                         accept_multiple_files=True)
        logo_subido = st.file_uploader("Logo (PNG, opcional)", type=["png"])
        color = st.color_picker("Color de marca", value=datos_marca["color"], key=f"color_{marca}")

    redes = st.multiselect(
        "Redes de la campaña", list(motor.REDES),
        default=["Telegram", "Bluesky", "Facebook", "Instagram", "LinkedIn", "X (Twitter)"],
        format_func=lambda r: {"auto": "🟢 ", "proxima": "🟡 ", "manual": "⬇️ "}[motor.REDES[r]["tipo"]] + r,
    )
    st.caption("🟢 publicación directa · 🟡 conexión directa próximamente · ⬇️ descarga para subir a mano")

    if st.button("Encargar campaña al equipo", type="primary"):
        if not descripcion.strip():
            st.warning("Describe qué quieres promocionar.")
        elif not redes:
            st.warning("Elige al menos una red.")
        else:
            brief = {"marca": marca, "descripcion": descripcion, "url": url.strip(),
                     "objetivo": objetivo, "mercado": mercado, "publico": publico, "oferta": oferta}
            fotos = [f.getvalue() for f in (fotos_subidas or [])]
            logo = logo_subido.getvalue() if logo_subido else None
            try:
                st.session_state.campana = ejecutar_campana(brief, fotos, logo, color,
                                                            redes, idioma, tono)
                st.success("Campaña lista. Tienes el trabajo del equipo en «Entregas».")
            except Exception as e:
                st.error(f"El equipo no pudo terminar la campaña: {e}")

# -------------------------------------------------------------------
# ENTREGAS
# -------------------------------------------------------------------
with tab_entregas:
    camp = st.session_state.campana
    if not camp:
        st.info("Aquí aparecerá el trabajo del equipo cuando encargues una campaña.")
    else:
        est = camp["estrategia"]

        with st.expander("Plan de campaña", expanded=True):
            firma("estrategia")
            st.write(est.get("resumen", ""))
            if est.get("mensaje_clave"):
                st.markdown(f"**Mensaje clave:** {est['mensaje_clave']}")
            st.markdown("**Público**")
            tabla(est.get("publico"))
            st.markdown("**Mercados**")
            tabla(est.get("mercados"))
            st.markdown("**Redes, horarios y frecuencia**")
            tabla(est.get("redes"))
            st.markdown("**Plan de 7 días**")
            tabla(est.get("plan_7_dias"))

        with st.expander("Textos de las publicaciones", expanded=True):
            firma("copy")
            st.caption("Puedes editar cualquier texto. {LINK} se sustituye por tu enlace con seguimiento.")
            for red in camp["redes"]:
                pub = camp["publicaciones"][red]
                st.markdown(f"**{red}**")
                pub["texto"] = st.text_area(red, pub.get("texto", ""), height=150,
                                            key=f"txt_{camp['id']}_{red}",
                                            label_visibility="collapsed")
                tags = st.text_input("Hashtags", " ".join(pub.get("hashtags", [])),
                                     key=f"tag_{camp['id']}_{red}")
                pub["hashtags"] = tags.split()
                final = motor.texto_final(pub, motor.enlace_utm(camp["brief"]["url"], red,
                                                                camp["nombre"]), red)
                st.caption(f"{len(final)} de {motor.REDES[red]['limite']} caracteres "
                           "con enlace y hashtags")
                if pub.get("variante_b"):
                    st.caption(f"Variante B: {pub['variante_b']}")

        with st.expander("Piezas visuales y guion de vídeo", expanded=True):
            firma("creativa")
            cols = st.columns(3)
            for i, red in enumerate(camp["redes"]):
                w, h = motor.REDES[red]["tamano"]
                with cols[i % 3]:
                    st.image(camp["piezas"][red], caption=f"{red} ({w}×{h})")
            st.markdown("---")
            st.markdown(camp["guion"])

# -------------------------------------------------------------------
# PUBLICACIÓN
# -------------------------------------------------------------------
with tab_publicar:
    camp = st.session_state.campana
    firma("community")
    if not camp:
        st.info("Cuando el equipo termine una campaña, aquí podrás publicarla.")
    else:
        textos = textos_campana(camp)
        horas = horarios(camp)
        st.download_button(
            "Descargar todo (ZIP)",
            motor.pack_zip(camp["redes"], camp["piezas"], textos, camp["guion"], camp["estrategia"]),
            file_name=f"{motor.slug(camp['nombre'])}.zip", mime="application/zip",
        )
        st.caption("Publica a la hora que recomienda Elena. La programación automática "
                   "llegará cuando conectemos la base de datos.")

        for red in camp["redes"]:
            tipo = motor.REDES[red]["tipo"]
            st.divider()
            c1, c2, c3 = st.columns([1, 2.2, 1])
            with c1:
                st.image(camp["piezas"][red], width=170)
            with c2:
                st.markdown(f"**{red}**")
                st.caption(motor.TIPOS[tipo])
                if horas.get(red):
                    st.caption(f"Mejor horario: {horas[red]}")
                st.code(textos[red], language=None, wrap_lines=True)
            with c3:
                clave = f"{camp['id']}_{red}"
                if tipo == "auto" and motor.conectado(red, SECRETOS):
                    if st.button(f"Publicar en {red}", key=f"pub_{clave}", type="primary"):
                        try:
                            enlace = motor.publicar(red, textos[red], camp["piezas"][red], SECRETOS)
                            st.session_state.registro.append(
                                {"campaña": camp["id"], "fecha": dt.datetime.now().strftime("%d/%m %H:%M"),
                                 "red": red, "estado": "Publicado", "enlace": enlace})
                            st.success("Publicado.")
                        except Exception as e:
                            st.error(f"No se pudo publicar en {red}: {e}")
                else:
                    if tipo == "auto":
                        st.caption("Sin conectar: añade sus claves en los Secrets.")
                    st.download_button("Descargar imagen", camp["piezas"][red],
                                       file_name=f"{motor.slug(red)}.jpg", mime="image/jpeg",
                                       key=f"img_{clave}")
                    st.download_button("Descargar texto", textos[red].encode("utf-8"),
                                       file_name=f"{motor.slug(red)}.txt", mime="text/plain",
                                       key=f"txtd_{clave}")
                    if st.button("Marcar como publicada", key=f"man_{clave}"):
                        st.session_state.registro.append(
                            {"campaña": camp["id"], "fecha": dt.datetime.now().strftime("%d/%m %H:%M"),
                             "red": red, "estado": "Publicado a mano", "enlace": ""})
                        st.success("Anotado.")

# -------------------------------------------------------------------
# RESULTADOS
# -------------------------------------------------------------------
with tab_resultados:
    firma("analista")
    camp = st.session_state.campana
    if st.session_state.registro:
        st.markdown("**Publicaciones hechas**")
        st.dataframe(pd.DataFrame(st.session_state.registro), hide_index=True,
                     column_config={"enlace": st.column_config.LinkColumn("Enlace")})
    else:
        st.info("Todavía no hay publicaciones registradas.")

    if camp:
        st.markdown("**Enlaces con seguimiento**")
        st.caption("Cada red lleva su propio enlace. En Google Analytics verás cuántas visitas "
                   "y registros trae cada una.")
        st.dataframe(pd.DataFrame([{"red": r, "enlace": motor.enlace_utm(camp["brief"]["url"], r,
                                                                          camp["nombre"])}
                                   for r in camp["redes"]]), hide_index=True)

        st.markdown("**Métricas de la campaña**")
        base = pd.DataFrame([{"red": r, "alcance": 0, "clics": 0, "visitas_web": 0,
                              "suscriptores": 0} for r in camp["redes"]])
        metricas = st.data_editor(base, hide_index=True, disabled=["red"],
                                  key=f"met_{camp['id']}")
        if st.button("Pedir informe a Sara"):
            with st.spinner("Sara está preparando el informe…"):
                try:
                    st.markdown(motor.informe_resultados(get_gemini_client(), MODELOS_VALIDOS,
                                                         camp["brief"],
                                                         metricas.to_dict("records"), idioma))
                except Exception as e:
                    st.error(f"No se pudo generar el informe: {e}")

# -------------------------------------------------------------------
# TALENTO
# -------------------------------------------------------------------
with tab_talento:
    firma("talento")
    render_buscador(get_gemini_client, MODELOS_VALIDOS)
