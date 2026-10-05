"""
Buscador de colaboradores, embajadores y afiliados para PublishFlow.

Fuentes:
  - YouTube Data API v3 (oficial)      -> necesita YOUTUBE_API_KEY en los Secrets
  - Bluesky (API pública, sin clave)
  - Agente Gemini con Google Search    -> Instagram, TikTok, webs y blogs

Uso en app.py:
    from buscador_colaboradores import render_buscador
    render_buscador(get_gemini_client, MODELOS_VALIDOS)
"""
import re
import json
import requests
import pandas as pd
import streamlit as st
from google.genai import types

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

RANGOS = {
    "Cualquiera": (0, 10**12),
    "Nano (1k - 10k)": (1_000, 10_000),
    "Micro (10k - 100k)": (10_000, 100_000),
    "Medio (100k - 500k)": (100_000, 500_000),
    "Grande (+500k)": (500_000, 10**12),
}

# País -> (regionCode de YouTube, idioma)
PAISES = {
    "España": ("ES", "es"),
    "México": ("MX", "es"),
    "Argentina": ("AR", "es"),
    "Colombia": ("CO", "es"),
    "Estados Unidos": ("US", "en"),
    "Reino Unido": ("GB", "en"),
    "Global (inglés)": (None, "en"),
}

MARCAS = {
    "AdeskCharts": (
        "Plataforma web de trading (adeskcharts.com) con screener de acciones tipo Finviz "
        "y agentes de IA que analizan las acciones filtradas. Mejor servicio que las "
        "alternativas por menos dinero. Suscripción de pago."
    ),
    "SoundSnip Studio PRO": (
        "Web de herramientas de audio: controlador DJ, mesa de estudio, efectos y editor. "
        "Para DJs, productores y creadores de contenido. Suscripción de pago."
    ),
    "Otra (personalizada)": "",
}

OFERTAS = [
    "Afiliado (comisión por cada venta con su código)",
    "Embajador (cuenta PRO gratis + comisión)",
    "Colaboración pagada (post o vídeo patrocinado)",
    "Intercambio (acceso gratis a cambio de reseña)",
]

ESTADOS = ["🔍 Encontrado", "✉️ Contactado", "💬 Respondió", "🤝 Colaborando", "❌ Descartado"]

COLUMNAS = ["afinidad", "nombre", "red", "seguidores", "media_vistas",
            "contacto", "url", "motivo", "descripcion"]


# -------------------------------------------------------------------
# Utilidades Gemini
# -------------------------------------------------------------------
def _llamar_gemini(client, modelos, contents, config=None):
    """Prueba los modelos en orden y devuelve el texto de la primera respuesta válida."""
    ultimo_error = None
    for modelo in modelos:
        try:
            r = client.models.generate_content(model=modelo, contents=contents, config=config)
            if r and r.text:
                return r.text
        except Exception as e:
            ultimo_error = e
    raise ultimo_error or RuntimeError("Sin respuesta de Gemini")


def _extraer_json(texto):
    """Extrae el primer array JSON de un texto (Gemini a veces añade texto o ```json)."""
    if not texto:
        return None
    i, j = texto.find("["), texto.rfind("]")
    if i == -1 or j == -1:
        return None
    try:
        return json.loads(texto[i:j + 1])
    except json.JSONDecodeError:
        return None


def _emails(texto):
    return ", ".join(sorted(set(EMAIL_RE.findall(texto or ""))))


# -------------------------------------------------------------------
# Fuentes de búsqueda
# -------------------------------------------------------------------
def buscar_youtube(consulta, pais, max_res=25):
    key = st.secrets.get("YOUTUBE_API_KEY", "")
    if not key:
        st.warning("Falta `YOUTUBE_API_KEY` en los Secrets: se omite YouTube.")
        return []

    region, idioma = PAISES[pais]
    params = {"part": "snippet", "type": "channel", "q": consulta,
              "maxResults": max_res, "relevanceLanguage": idioma, "key": key}
    if region:
        params["regionCode"] = region

    r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=10)
    r.raise_for_status()
    ids = [it["id"]["channelId"] for it in r.json().get("items", [])
           if it.get("id", {}).get("channelId")]
    if not ids:
        return []

    r2 = requests.get("https://www.googleapis.com/youtube/v3/channels",
                      params={"part": "snippet,statistics", "id": ",".join(ids), "key": key},
                      timeout=10)
    r2.raise_for_status()

    resultados = []
    for c in r2.json().get("items", []):
        sn, stats = c["snippet"], c.get("statistics", {})
        subs = int(stats.get("subscriberCount", 0) or 0)
        videos = int(stats.get("videoCount", 0) or 0)
        vistas = int(stats.get("viewCount", 0) or 0)
        desc = sn.get("description", "")
        handle = sn.get("customUrl")
        resultados.append({
            "nombre": sn.get("title", ""),
            "red": "YouTube",
            "url": f"https://www.youtube.com/{handle}" if handle
                   else f"https://www.youtube.com/channel/{c['id']}",
            "seguidores": subs,
            "media_vistas": vistas // videos if videos else 0,
            "contacto": _emails(desc),
            "descripcion": desc[:300],
        })
    return resultados


def buscar_bluesky(consulta, max_res=25):
    base = "https://public.api.bsky.app/xrpc/"
    r = requests.get(base + "app.bsky.actor.searchActors",
                     params={"q": consulta, "limit": max_res}, timeout=10)
    r.raise_for_status()
    handles = [a["handle"] for a in r.json().get("actors", [])]
    if not handles:
        return []

    r2 = requests.get(base + "app.bsky.actor.getProfiles",
                      params={"actors": handles}, timeout=10)
    r2.raise_for_status()

    resultados = []
    for p in r2.json().get("profiles", []):
        desc = p.get("description", "") or ""
        resultados.append({
            "nombre": p.get("displayName") or p["handle"],
            "red": "Bluesky",
            "url": f"https://bsky.app/profile/{p['handle']}",
            "seguidores": int(p.get("followersCount", 0) or 0),
            "media_vistas": None,
            "contacto": _emails(desc),
            "descripcion": desc[:300],
        })
    return resultados


def buscar_con_ia(client, modelos, marca_desc, nicho, redes, rango, pais, n=10):
    """Agente Gemini con Google Search para redes sin API de búsqueda pública."""
    prompt = f"""
Eres un especialista en marketing de influencers. Usa la búsqueda de Google para encontrar
{n} creadores de contenido o profesionales REALES que podrían colaborar como embajadores
o afiliados de este producto.

PRODUCTO: {marca_desc}
NICHO / TEMÁTICA: {nicho}
REDES: {", ".join(redes)}
TAMAÑO DE AUDIENCIA: {rango}
PAÍS / IDIOMA: {pais}

Reglas:
- Solo cuentas que aparezcan en tus resultados de búsqueda. No inventes nombres, enlaces ni cifras.
- Prioriza cuentas activas con una vía de contacto profesional pública
  (email de negocios, web, formulario, "para colaboraciones").
- Si no conoces un dato, deja el campo vacío o a 0.

Responde ÚNICAMENTE con un array JSON, sin texto adicional, con objetos así:
{{"nombre": "", "red": "", "url": "", "seguidores": 0, "contacto": "", "descripcion": "por qué encaja, en una frase"}}
"""
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    datos = _extraer_json(_llamar_gemini(client, modelos, prompt, config)) or []

    resultados = []
    for d in datos:
        if not isinstance(d, dict) or not d.get("url"):
            continue
        try:
            seguidores = int(d.get("seguidores") or 0)
        except (TypeError, ValueError):
            seguidores = 0
        resultados.append({
            "nombre": str(d.get("nombre", "")),
            "red": f"{d.get('red', 'Web')} (IA)",
            "url": str(d["url"]),
            "seguidores": seguidores,
            "media_vistas": None,
            "contacto": str(d.get("contacto", "")),
            "descripcion": str(d.get("descripcion", ""))[:300],
        })
    return resultados


# -------------------------------------------------------------------
# IA: afinidad y mensaje de contacto
# -------------------------------------------------------------------
def puntuar_afinidad(client, modelos, marca_desc, candidatos):
    if not candidatos:
        return candidatos
    resumen = [{"i": i, "nombre": c["nombre"], "red": c["red"],
                "seguidores": c["seguidores"], "descripcion": c["descripcion"]}
               for i, c in enumerate(candidatos)]
    prompt = f"""
Puntúa de 1 a 10 la afinidad de cada cuenta para promocionar este producto como embajador
o afiliado. Valora que la temática y el público coincidan, y penaliza cuentas que no parezcan
de creadores reales o activos.

PRODUCTO: {marca_desc}
CUENTAS: {json.dumps(resumen, ensure_ascii=False)}

Responde SOLO con un array JSON: [{{"i": 0, "afinidad": 7, "motivo": "frase corta"}}]
"""
    try:
        datos = _extraer_json(_llamar_gemini(client, modelos, prompt)) or []
    except Exception:
        datos = []
    for d in datos:
        try:
            i = int(d["i"])
            candidatos[i]["afinidad"] = int(d.get("afinidad", 0))
            candidatos[i]["motivo"] = str(d.get("motivo", ""))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return candidatos


def generar_mensaje(client, modelos, marca, marca_desc, oferta, creador, idioma):
    prompt = f"""
Escribe un primer mensaje de contacto breve (máximo 120 palabras) en {idioma} para proponer
una colaboración.

Marca: {marca} — {marca_desc}
Propuesta: {oferta}
Creador: {creador['nombre']} ({creador['red']}) — {creador.get('descripcion', '')}

Requisitos:
- Empieza con una línea "Asunto: ...".
- Personalizado: menciona algo concreto de su temática, sin inventar datos.
- Tono cercano y profesional, sin presión.
- Explica qué gana su audiencia y qué gana él/ella.
- Termina con una pregunta sencilla y una frase indicando que, si no le interesa,
  no volverás a escribir.
"""
    return _llamar_gemini(client, modelos, prompt)


# -------------------------------------------------------------------
# Interfaz Streamlit
# -------------------------------------------------------------------
def render_buscador(get_client, modelos):
    st.subheader("🤝 Buscador de colaboradores, embajadores y afiliados")
    st.caption(
        "Usa solo contactos profesionales públicos, escribe uno a uno con mensajes "
        "personalizados y respeta a quien no quiera colaborar (RGPD)."
    )

    st.session_state.setdefault("colaboradores", [])
    st.session_state.setdefault("resultados", [])

    c1, c2 = st.columns(2)
    with c1:
        marca = st.selectbox("Marca a promocionar", list(MARCAS), key="col_marca")
        marca_desc = st.text_area("Descripción del producto", value=MARCAS[marca],
                                  height=100, key=f"col_desc_{marca}")
        nicho = st.text_input("Nicho o palabras clave",
                              placeholder="Ej.: trading acciones / DJ techno / producción musical",
                              key="col_nicho")
    with c2:
        redes = st.multiselect(
            "Dónde buscar",
            ["YouTube (API oficial)", "Bluesky (API pública)",
             "Instagram (agente IA)", "TikTok (agente IA)", "Webs y blogs (agente IA)"],
            default=["YouTube (API oficial)", "Bluesky (API pública)"],
            key="col_redes",
        )
        rango = st.selectbox("Tamaño de audiencia", list(RANGOS), index=2, key="col_rango")
        pais = st.selectbox("País / idioma", list(PAISES), key="col_pais")
        solo_contacto = st.checkbox("Solo cuentas con contacto público visible", key="col_solo")

    oferta = st.selectbox("Tipo de colaboración que ofreces", OFERTAS, key="col_oferta")

    # --- Búsqueda ---
    if st.button("🔎 Buscar candidatos", type="primary", key="btn_col_buscar"):
        if not nicho.strip():
            st.warning("Escribe un nicho o palabras clave.")
        elif not redes:
            st.warning("Elige al menos un sitio donde buscar.")
        else:
            client = get_client()
            res = []
            with st.spinner("Buscando cuentas..."):
                if "YouTube (API oficial)" in redes:
                    try:
                        res += buscar_youtube(nicho, pais)
                    except Exception as e:
                        st.error(f"YouTube: {e}")
                if "Bluesky (API pública)" in redes:
                    try:
                        res += buscar_bluesky(nicho)
                    except Exception as e:
                        st.error(f"Bluesky: {e}")
                redes_ia = [r.split(" (")[0] for r in redes if "agente IA" in r]
                if redes_ia:
                    try:
                        res += buscar_con_ia(client, modelos, marca_desc, nicho,
                                             redes_ia, rango, pais)
                    except Exception as e:
                        st.error(f"Agente IA: {e}")

            minimo, maximo = RANGOS[rango]
            res = [r for r in res
                   if (r["red"].endswith("(IA)") and not r["seguidores"])
                   or minimo <= r["seguidores"] <= maximo]
            if solo_contacto:
                res = [r for r in res if r["contacto"]]

            with st.spinner("Valorando afinidad con IA..."):
                res = puntuar_afinidad(client, modelos, marca_desc, res)
            res.sort(key=lambda r: r.get("afinidad", 0), reverse=True)
            st.session_state.resultados = res

    # --- Resultados ---
    res = st.session_state.resultados
    if res:
        st.markdown(f"**{len(res)} candidatos encontrados**")
        if any(r["red"].endswith("(IA)") for r in res):
            st.info("Los resultados del agente IA pueden tener errores: abre el enlace y "
                    "comprueba la cuenta antes de contactar.")

        df = pd.DataFrame(res).reindex(columns=COLUMNAS)
        df.insert(0, "guardar", False)
        editado = st.data_editor(
            df,
            column_config={
                "guardar": st.column_config.CheckboxColumn("💾"),
                "afinidad": st.column_config.ProgressColumn("Afinidad", min_value=0,
                                                            max_value=10, format="%d"),
                "url": st.column_config.LinkColumn("Enlace"),
                "media_vistas": st.column_config.NumberColumn("Media vistas/vídeo"),
            },
            disabled=[c for c in df.columns if c != "guardar"],
            hide_index=True,
            use_container_width=True,
            key="tabla_resultados",
        )

        if st.button("💾 Guardar seleccionados en mi lista", key="btn_col_guardar"):
            existentes = {c["url"] for c in st.session_state.colaboradores}
            nuevos = 0
            for _, fila in editado[editado["guardar"]].iterrows():
                if fila["url"] in existentes:
                    continue
                d = {k: fila[k] for k in COLUMNAS}
                d.update(marca=marca, estado=ESTADOS[0], notas="")
                st.session_state.colaboradores.append(d)
                nuevos += 1
            st.success(f"{nuevos} añadidos a tu lista.")

    # --- Mini CRM ---
    st.divider()
    st.subheader("📋 Mi lista de colaboradores")
    lista = st.session_state.colaboradores
    if not lista:
        st.caption("Aún no has guardado ninguno.")
        return

    crm = pd.DataFrame(lista)
    vista = crm[["estado", "marca", "nombre", "red", "seguidores", "contacto", "url", "notas"]]
    crm_editado = st.data_editor(
        vista,
        column_config={
            "estado": st.column_config.SelectboxColumn("Estado", options=ESTADOS),
            "url": st.column_config.LinkColumn("Enlace"),
        },
        disabled=["marca", "nombre", "red", "seguidores", "url"],
        hide_index=True,
        use_container_width=True,
        key="tabla_crm",
    )
    for i, fila in crm_editado.iterrows():
        lista[i].update(estado=fila["estado"], contacto=fila["contacto"], notas=fila["notas"])

    st.download_button("⬇️ Descargar lista (CSV)",
                       pd.DataFrame(lista).to_csv(index=False).encode("utf-8-sig"),
                       "colaboradores.csv", "text/csv", key="btn_col_csv")

    # --- Mensaje de contacto ---
    st.markdown("#### ✍️ Mensaje de contacto personalizado")
    nombres = [f"{c['nombre']} ({c['red']})" for c in lista]
    sel = st.selectbox("Para:", range(len(nombres)), format_func=lambda i: nombres[i],
                       key="col_sel")
    idioma_msg = st.selectbox("Idioma del mensaje", ["Español", "Inglés"], key="col_idioma")

    if st.button("✍️ Redactar mensaje", key="btn_col_msg"):
        c = lista[sel]
        desc = MARCAS.get(c["marca"]) or marca_desc
        with st.spinner("Redactando..."):
            try:
                st.session_state.col_mensaje = generar_mensaje(
                    get_client(), modelos, c["marca"], desc, oferta, c, idioma_msg)
            except Exception as e:
                st.error(f"Error al generar el mensaje: {e}")

    if st.session_state.get("col_mensaje"):
        st.text_area("Revísalo y envíalo tú desde la red social o tu email:",
                     st.session_state.col_mensaje, height=230,
                     key=f"col_msg_{hash(st.session_state.col_mensaje)}")
