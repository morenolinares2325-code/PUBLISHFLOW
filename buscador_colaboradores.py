# buscador_colaboradores.py
import json
import datetime as dt

import streamlit as st

from almacen_talentos import (
    TTL_HORAS_DEFECTO, ESTADOS_CONTACTO,
    buscar_en_cache, guardar_resultado, listar_busquedas,
    actualizar_contacto, borrar_busqueda, limpiar_caducadas, resumen_metricas,
)

# Reutilizamos el estilo .firma ya definido en app.py
def _firma(id_miembro):
    # Si tu app.py ya expone una función firma(), impórtala en su lugar.
    try:
        from app import firma as _f  # noqa
        return _f(id_miembro)
    except Exception:
        pass


# -------------------------------------------------------------------
# Prompt acotado (una sola llamada, JSON estricto, límite duro)
# -------------------------------------------------------------------
PROMPT_PROSPECCION = """Eres Javier Romero, ojeador de talento de PublishFlow.
Devuelve EXACTAMENTE {max_resultados} oportunidades. Ni una más, ni una menos.

## Briefing
- Nicho: {nicho}
- Plataforma principal: {plataforma}
- Mercado: {pais}
- Idioma del creador: {idioma_creador}
- Rango de seguidores: {seguidores}
- Marca que representas: {marca}

## Reglas estrictas
1. Si no estás seguro de un nombre real verificable, usa un ARQUETIPO
   descriptivo (ej.: "canal de reseñas de synths en YouTube ES, ~30k subs")
   y rellena "enlace_o_busqueda" con una query de búsqueda útil.
2. Cada oportunidad DEBE respetar el esquema JSON de abajo.
3. Prohibido añadir texto fuera del JSON.
4. Si no encuentras {max_resultados} candidatos creíbles, devuelve menos.

## Esquema JSON (array de objetos)
[
  {{
    "nombre_o_arquetipo": "string",
    "plataforma": "string",
    "enlace_o_busqueda": "string",
    "seguidores_estimados": "string",
    "afinidad": 0,
    "por_que_encaja": "máx 25 palabras",
    "mensaje_contacto": "máx 60 palabras"
  }}
]

Responde SOLO con el array JSON."""


def _parsear_json_seguro(texto):
    """Tolera ```json ... ``` o texto alrededor del array."""
    if not texto:
        return []
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    ini, fin = t.find("["), t.rfind("]")
    if ini == -1 or fin == -1:
        return []
    try:
        data = json.loads(t[ini:fin + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _buscar_oportunidades_ia(get_gemini_client, modelos, filtros, cred):
    gestor = get_gemini_client() if callable(get_gemini_client) else get_gemini_client
    prompt = PROMPT_PROSPECCION.format(**filtros)
    # Si tu GestorIA expone .generar(prompt, modelos=...), ajústalo aquí.
    # Fallback por si la firma es distinta:
    try:
        respuesta = gestor.generar(prompt, modelos=modelos,
                                   temperatura=0.4, max_tokens=1500)
    except TypeError:
        respuesta = gestor.generar(prompt, modelos=modelos)
    resultados = _parsear_json_seguro(respuesta)
    fuente = getattr(gestor, "ultimo_proveedor", "ia")
    return resultados, fuente


# -------------------------------------------------------------------
# Formulario de filtros
# -------------------------------------------------------------------
def _formulario_filtros(marca_actual="AdeskCharts"):
    c1, c2, c3 = st.columns(3)
    with c1:
        nicho = st.text_input("Nicho o sector",
                              placeholder="Ej.: productividad, música lo-fi",
                              key="tal_nicho")
        plataforma = st.selectbox("Plataforma principal",
                                  ["Cualquiera", "YouTube", "TikTok", "Instagram",
                                   "X (Twitter)", "Twitch", "Newsletter", "Blog"],
                                  key="tal_plat")
    with c2:
        pais = st.selectbox("Mercado",
                            ["Global", "España", "LATAM", "USA", "Europa"],
                            key="tal_pais")
        idioma = st.selectbox("Idioma del creador",
                              ["Español", "Inglés", "Portugués", "Cualquiera"],
                              key="tal_idioma")
    with c3:
        seguidores = st.select_slider("Rango de seguidores",
                                      options=["Nano (1-10k)", "Micro (10-50k)",
                                               "Medio (50-200k)", "Macro (200k-1M)",
                                               "Cualquiera"],
                                      value="Micro (10-50k)",
                                      key="tal_seg")
        max_resultados = st.slider("Nº máximo de oportunidades", 3, 10, 5,
                                   key="tal_max")
    ttl = st.select_slider("Caducidad de esta búsqueda",
                           options=[24, 72, 168, 336, 720], value=168,
                           format_func=lambda h: f"{h//24} días",
                           key="tal_ttl")
    return {
        "nicho": nicho, "plataforma": plataforma, "pais": pais,
        "idioma_creador": idioma, "seguidores": seguidores,
        "max_resultados": max_resultados, "marca": marca_actual,
        "ttl_horas": ttl,
    }


# -------------------------------------------------------------------
# Pintado reutilizable (lo usan Buscar y Base)
# -------------------------------------------------------------------
def _pintar_resultados(registro, editable=True):
    st.caption(f"🔑 {registro.get('clave_legible','')} · "
               f"fuente: {registro.get('fuente','?')} · id: {registro['id']}")

    for i, item in enumerate(registro["resultados"]):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### {item.get('nombre_o_arquetipo','—')}")
                st.caption(f"{item.get('plataforma','—')} · "
                           f"{item.get('seguidores_estimados','—')} · "
                           f"afinidad **{item.get('afinidad','—')}%**")
                if item.get("por_que_encaja"):
                    st.write(item["por_que_encaja"])
                if item.get("mensaje_contacto"):
                    st.markdown("**Mensaje de contacto sugerido:**")
                    st.code(item["mensaje_contacto"], language=None, wrap_lines=True)
                if item.get("enlace_o_busqueda"):
                    st.markdown(f"🔗 [Abrir / buscar]({item['enlace_o_busqueda']})")
            with c2:
                if not editable:
                    st.caption(f"Estado: {item.get('estado_contacto','pendiente')}")
                    if item.get("notas"):
                        st.caption(f"Notas: {item['notas']}")
                    continue
                actual = item.get("estado_contacto", "pendiente")
                nuevo = st.selectbox(
                    "Estado", ESTADOS_CONTACTO,
                    index=ESTADOS_CONTACTO.index(actual) if actual in ESTADOS_CONTACTO else 0,
                    key=f"est_{registro['id']}_{i}",
                )
                notas = st.text_area("Notas", item.get("notas", ""),
                                     key=f"not_{registro['id']}_{i}", height=80)
                if (nuevo != actual) or (notas != item.get("notas", "")):
                    if st.button("💾 Guardar cambios",
                                 key=f"sv_{registro['id']}_{i}"):
                        actualizar_contacto(registro["id"], i, nuevo, notas)
                        st.success("Actualizado.")
                        st.rerun()


# -------------------------------------------------------------------
# Base de talentos (nueva vista)
# -------------------------------------------------------------------
def _pintar_base():
    _firma("talento")
    st.subheader("Prospecciones guardadas")

    busquedas = listar_busquedas()
    if not busquedas:
        st.info("Aún no hay búsquedas guardadas. Lanza una desde «Buscar».")
        return

    marcas = sorted({b.get("marca", "—") for b in busquedas})
    marca_sel = st.multiselect("Filtrar por marca", marcas, default=marcas,
                               key="tal_filtro_marca")

    m = resumen_metricas()
    c1, c2, c3 = st.columns(3)
    c1.metric("Prospecciones", m["prospecciones"])
    c2.metric("Creadores en base", m["creadores"])
    c3.metric("Pendientes de contacto", m["pendientes"])

    for b in busquedas:
        if b.get("marca") not in marca_sel:
            continue
        etiqueta = (f"📌 {b.get('clave_legible','—')} · "
                    f"{len(b.get('resultados', []))} perfiles · "
                    f"{b.get('fecha','')[:16].replace('T', ' ')}")
        with st.expander(etiqueta):
            _pintar_resultados(b, editable=True)
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("🗑️ Borrar", key=f"del_{b['id']}"):
                    borrar_busqueda(b["id"])
                    st.rerun()

    st.divider()
    if st.button("🧹 Limpiar búsquedas caducadas (>7 días)"):
        n = limpiar_caducadas()
        st.success(f"Se borraron {n} prospecciones caducadas.")
        st.rerun()


# -------------------------------------------------------------------
# API pública: se llama exactamente igual que antes
# -------------------------------------------------------------------
def render_buscador(get_gemini_client, MODELOS_VALIDOS, CRED):
    sub_buscar, sub_base = st.tabs(["🔎 Buscar", "🗂️ Base de talentos"])

    with sub_buscar:
        _firma("talento")
        st.subheader("Buscador de talentos — Javier Romero")

        filtros = _formulario_filtros()

        col_a, col_b = st.columns([4, 1])
        with col_b:
            forzar = st.checkbox("Forzar nueva búsqueda", value=False,
                                 key="tal_forzar",
                                 help="Ignora la caché aunque exista.")

        # 1) Caché
        if not forzar:
            cacheado = buscar_en_cache(filtros, ttl_horas=filtros["ttl_horas"])
            if cacheado:
                st.success(
                    f"⚡ Recuperado de la base (guardado el "
                    f"{cacheado['fecha'][:16].replace('T',' ')}). Sin gastar tokens."
                )
                if len(cacheado["resultados"]) < filtros["max_resultados"]:
                    st.info(
                        f"En base hay {len(cacheado['resultados'])} perfiles. "
                        "Marca «Forzar nueva búsqueda» para ampliar."
                    )
                _pintar_resultados(cacheado)
                return

        # 2) IA
        if not filtros["nicho"].strip():
            st.warning("Escribe al menos un nicho.")
            return

        with st.spinner(
            f"Javier está ojeando {filtros['max_resultados']} perfiles en "
            f"{filtros['plataforma']}…"
        ):
            try:
                resultados, fuente = _buscar_oportunidades_ia(
                    get_gemini_client, MODELOS_VALIDOS, filtros, CRED
                )
            except Exception as e:
                st.error(f"Javier no pudo terminar la búsqueda: {e}")
                return

        if not resultados:
            st.warning("Javier no encontró oportunidades con estos filtros. "
                       "Prueba a ampliar el rango de seguidores o el mercado.")
            return

        # 3) Guardar
        registro = guardar_resultado(
            filtros, resultados,
            marca=filtros.get("marca", "—"),
            fuente=fuente,
            ttl_horas=filtros["ttl_horas"],
        )
        st.success(
            f"✅ {len(resultados)} oportunidades guardadas "
            f"(id `{registro['id']}`). La próxima vez no se llamará a la IA."
        )
        _pintar_resultados(registro)

    with sub_base:
        _pintar_base()
