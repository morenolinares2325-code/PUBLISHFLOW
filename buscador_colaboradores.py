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

SECTORES = {
    "Trading e inversión": "trading, bolsa, análisis técnico, inversión, acciones, mercados financieros",
    "Criptomonedas": "criptomonedas, bitcoin, blockchain, trading de cripto",
    "Finanzas personales": "finanzas personales, ahorro, libertad financiera, educación financiera",
    "DJs y música electrónica": "DJ, música electrónica, sesiones, techno, house, mezclas",
    "Producción musical": "producción musical, beats, home studio, mezcla y mastering, productores",
    "Creadores de contenido y audio": "creadores de contenido, podcast, edición de audio, YouTubers",
    "Tecnología e IA": "inteligencia artificial, herramientas digitales, tecnología, software, SaaS",
    "Emprendimiento y marketing": "emprendimiento, negocios online, marketing digital, startups",
}
SECTOR_POR_MARCA = {"AdeskCharts": "Trading e inversión",
                    "SoundSnip Studio PRO": "DJs y música electrónica"}

PERFILES = ["Creadores de contenido / influencers", "Educadores y formadores",
            "Comunidades y grupos", "Medios, blogs y newsletters", "Podcasts",
            "Profesionales del sector", "Empresas o marcas complementarias"]

SITIOS_API = {"YouTube (datos oficiales)": "youtube", "Bluesky (datos oficiales)": "bluesky"}
SITIOS_IA = ["Instagram", "TikTok", "X (Twitter)", "LinkedIn", "Twitch", "Facebook (páginas y grupos)",
             "Telegram (canales)", "Discord (servidores)", "Reddit (comunidades)",
             "Podcasts (Spotify / Apple)", "Newsletters (Substack y similares)", "Webs y blogs",
             "Threads"]

ESTADOS = ["🔍 Encontrado", "✉️ Contactado", "💬 Respondió", "🤝 Colaborando", "❌ Descartado"]

COLUMNAS = ["afinidad", "nombre", "red", "tipo", "seguidores", "interaccion", "verificado", "media_vistas",
            "contacto", "url", "motivo", "descripcion"]


# -------------------------------------------------------------------
# Utilidades Gemini
# -------------------------------------------------------------------
def _llamar_gemini(client, modelos, contents, config=None):
    """Prueba los modelos en orden y devuelve el texto de la primera respuesta válida."""
    if hasattr(client, "generar"):   # Gestor de IA con varias claves
        partes = contents if isinstance(contents, list) else [contents]
        texto = "\n".join(p for p in partes if isinstance(p, str))
        return client.generar(texto, buscar_web=config is not None)
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
    """Extrae una lista JSON de un texto (acepta ```json, texto alrededor o {"cuentas": [...]})."""
    if not texto:
        return None
    limpio = re.sub(r"```(?:json)?", "", texto)
    decodificador = json.JSONDecoder()
    for i, caracter in enumerate(limpio):
        if caracter not in "[{":
            continue
        try:
            datos, _ = decodificador.raw_decode(limpio[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(datos, list) and any(isinstance(d, dict) for d in datos):
            return datos
        if isinstance(datos, dict):
            for valor in datos.values():
                if isinstance(valor, list):
                    return valor
    return None


def _emails(texto):
    return ", ".join(sorted(set(EMAIL_RE.findall(texto or ""))))


# -------------------------------------------------------------------
# Fuentes de búsqueda
# -------------------------------------------------------------------
def buscar_youtube(consulta, pais, max_res=25, key=None):
    if not key:
        try:
            key = st.secrets.get("YOUTUBE_API_KEY", "")
        except Exception:
            key = ""
    if not key:
        raise RuntimeError("falta YOUTUBE_API_KEY en los Secrets. Es gratis: "
                           "console.cloud.google.com → activa «YouTube Data API v3» → "
                           "Credenciales → Crear clave de API.")

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


def buscar_con_ia(client, modelos, marca_desc, sector, extra, perfiles, redes, rango, pais,
                  n=30, diag=None):
    """Agente IA con búsqueda web: candidatos del sector en varias redes, en una sola llamada."""
    prompt = f"""
Eres un especialista en marketing de influencers y alianzas. Usa la búsqueda web para encontrar
{n} perfiles REALES del sector indicado que podrían colaborar como embajadores, afiliados o
colaboradores de una marca.

SECTOR: {sector}
TEMAS DEL SECTOR: {SECTORES.get(sector, sector)}
PALABRAS CLAVE EXTRA: {extra or "(ninguna)"}
TIPO DE PERFIL: {", ".join(perfiles) or "cualquiera"}
DÓNDE BUSCAR: {", ".join(redes)}
TAMAÑO DE AUDIENCIA PREFERIDO: {rango}
PAÍS / IDIOMA: {pais}
MARCA (solo como contexto): {marca_desc}

Reglas:
- Reparte los resultados entre los sitios indicados.
- Solo perfiles que aparezcan en tus resultados de búsqueda. No inventes nombres, enlaces ni cifras.
- Prioriza perfiles activos con vía de contacto profesional pública (email de negocios, web,
  formulario, "para colaboraciones").
- Enlaza siempre al perfil, no a una publicación: https://www.instagram.com/usuario/ ,
  https://www.tiktok.com/@usuario , https://x.com/usuario , etc.
- Si no conoces un dato, deja el campo vacío o a 0.
- Si no encuentras suficientes del tamaño pedido, incluye también perfiles algo mayores o menores.

Responde ÚNICAMENTE con un array JSON, sin texto adicional, con objetos así:
{{"nombre": "", "red": "", "tipo": "", "url": "", "seguidores": 0, "contacto": "",
  "descripcion": "de qué trata y por qué encaja, en una frase"}}
"""
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    texto = _llamar_gemini(client, modelos, prompt, config)
    datos = _extraer_json(texto)
    if datos is None and diag is not None:
        if re.search(r"browse|navegar|real-time|tiempo real", texto or "", re.I):
            diag.append("La IA que respondió no tiene búsqueda en internet. Para buscar en "
                        "Instagram, TikTok y webs hace falta que Gemini funcione (usa la búsqueda "
                        "de Google). Revisa tu clave en la barra lateral → Diagnóstico de claves.")
        else:
            diag.append("El agente IA respondió, pero no en el formato esperado: "
                        + (texto or "(vacío)")[:300])
    datos = datos or []

    resultados, vistos = [], set()
    for d in datos:
        if not isinstance(d, dict) or not d.get("url"):
            continue
        url = str(d["url"]).strip()
        if url.lower().rstrip("/") in vistos:
            continue
        vistos.add(url.lower().rstrip("/"))
        try:
            seguidores = int(str(d.get("seguidores") or 0).replace(".", "").replace(",", ""))
        except (TypeError, ValueError):
            seguidores = 0
        resultados.append({
            "nombre": str(d.get("nombre", "")),
            "red": f"{d.get('red', 'Web')} (IA)",
            "tipo": str(d.get("tipo", "")),
            "url": url,
            "seguidores": seguidores,
            "media_vistas": None,
            "contacto": str(d.get("contacto", "")),
            "descripcion": str(d.get("descripcion", ""))[:300],
        })
    return resultados


def usuario_instagram(url):
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", url or "")
    if not m or m.group(1).lower() in ("p", "reel", "explore", "stories", "accounts"):
        return ""
    return m.group(1)


def verificar_instagram(usuario, cred):
    """Datos reales de una cuenta profesional de Instagram (API Business Discovery de Meta).
    Necesita Instagram conectado en la pestaña Conexiones."""
    version = cred.get("FB_GRAPH_VERSION") or "v23.0"
    campos = (f"business_discovery.username({usuario})"
              "{username,name,biography,website,followers_count,media_count,"
              "media.limit(6){like_count,comments_count}}")
    r = requests.get(f"https://graph.facebook.com/{version}/{cred['IG_USER_ID']}",
                     params={"fields": campos, "access_token": cred["FB_PAGE_TOKEN"]},
                     timeout=20)
    datos = r.json()
    if "error" in datos:
        raise RuntimeError(datos["error"].get("message", "Cuenta no verificable"))
    bd = datos["business_discovery"]
    seguidores = int(bd.get("followers_count") or 0)
    medias = (bd.get("media") or {}).get("data", [])
    interaccion = 0.0
    if medias and seguidores:
        media_int = sum((p.get("like_count") or 0) + (p.get("comments_count") or 0)
                        for p in medias) / len(medias)
        interaccion = round(100 * media_int / seguidores, 2)
    bio = bd.get("biography", "") or ""
    contacto = ", ".join(x for x in [_emails(bio), bd.get("website", "")] if x)
    return {"seguidores": seguidores, "interaccion": interaccion,
            "contacto": contacto, "bio": bio[:300], "nombre": bd.get("name") or usuario}


def instagram_conectado(cred):
    return bool(cred and cred.get("IG_USER_ID") and cred.get("FB_PAGE_TOKEN"))


# -------------------------------------------------------------------
# IA: afinidad y mensaje de contacto
# -------------------------------------------------------------------
def seleccionar_mejores(client, modelos, marca_desc, sector, rango, candidatos, top=20):
    """La IA puntúa a todos los candidatos y se quedan solo los mejores."""
    if not candidatos:
        return candidatos
    resumen = [{"i": i, "nombre": c["nombre"], "red": c["red"], "tipo": c.get("tipo", ""),
                "seguidores": c["seguidores"], "interaccion": c.get("interaccion"),
                "verificado": c.get("verificado", ""), "tiene_contacto": bool(c["contacto"]),
                "descripcion": c["descripcion"]}
               for i, c in enumerate(candidatos)]
    prompt = f"""
Eres responsable de alianzas de una marca. Puntúa de 1 a 10 cada perfil como posible embajador,
afiliado o colaborador.

SECTOR BUSCADO: {sector}
TAMAÑO DE AUDIENCIA PREFERIDO: {rango}
MARCA: {marca_desc}

Criterios, por orden de importancia:
1. Que su temática y su público encajen con el sector.
2. Que parezca un perfil real y activo (los datos verificados valen más).
3. Que tenga una vía de contacto pública.
4. Que su tamaño se acerque al preferido y, si se conoce, buena interacción.
Penaliza duplicados, perfiles genéricos, marcas competidoras directas y cuentas dudosas.

PERFILES: {json.dumps(resumen, ensure_ascii=False)}

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
    candidatos.sort(key=lambda c: (c.get("afinidad", 0), bool(c["contacto"]),
                                   c.get("verificado") == "✅ real"), reverse=True)
    return candidatos[:top]


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
def render_buscador(get_client, modelos, cred=None):
    st.subheader("🤝 Buscador de colaboradores, embajadores y afiliados")
    st.caption(
        "Usa solo contactos profesionales públicos, escribe uno a uno con mensajes "
        "personalizados y respeta a quien no quiera colaborar (RGPD)."
    )

    st.session_state.setdefault("colaboradores", [])
    st.session_state.setdefault("resultados", [])

    c1, c2 = st.columns(2)
    with c1:
        marca = st.selectbox("Marca para la que buscas", list(MARCAS), key="col_marca")
        marca_desc = MARCAS[marca]
        if not marca_desc:
            marca_desc = st.text_input("¿Qué es tu marca? (una frase)", key="col_desc_otra")
        sectores = list(SECTORES)
        sector = st.selectbox("Sector de los colaboradores", sectores,
                              index=sectores.index(SECTOR_POR_MARCA.get(marca, sectores[0])),
                              key=f"col_sector_{marca}")
        extra = st.text_input("Palabras clave extra (opcional)",
                              placeholder="Ej.: análisis técnico, day trading, techno",
                              key="col_extra")
        perfiles = st.multiselect("Tipo de perfil", PERFILES,
                                  default=["Creadores de contenido / influencers",
                                           "Educadores y formadores"],
                                  key="col_perfiles")
    with c2:
        redes = st.multiselect(
            "Dónde buscar", list(SITIOS_API) + SITIOS_IA,
            default=["Instagram", "YouTube (datos oficiales)", "TikTok", "X (Twitter)"],
            key="col_redes",
        )
        rango = st.selectbox("Tamaño de audiencia", list(RANGOS), index=2, key="col_rango")
        pais = st.selectbox("País / idioma", list(PAISES), key="col_pais")
        top = st.slider("Quedarme con los mejores", 5, 30, 20, key="col_top",
                        help="La IA revisa todos los perfiles encontrados y te deja solo estos.")
        solo_contacto = st.checkbox("Solo perfiles con contacto público visible", key="col_solo")
        if instagram_conectado(cred):
            st.caption("✅ Instagram conectado: verificaré seguidores, interacción y contacto reales "
                       "de las cuentas profesionales.")
        else:
            st.caption("ℹ️ Conecta Instagram en 🔌 Conexiones para verificar los perfiles con datos reales.")

    oferta = st.selectbox("Tipo de colaboración que ofreces", OFERTAS, key="col_oferta")

    # --- Búsqueda ---
    if st.button("🔎 Buscar candidatos", type="primary", key="btn_col_buscar"):
        consulta = f"{sector} {extra}".strip()
        if not redes:
            st.warning("Elige al menos un sitio donde buscar.")
        else:
            client = get_client()
            res, diag = [], []
            terminos = [extra] if extra.strip() else [t.strip() for t in
                                                     SECTORES[sector].split(",")[:2]]
            with st.spinner("Buscando perfiles del sector..."):
                if "YouTube (datos oficiales)" in redes:
                    try:
                        encontrados = []
                        for t in terminos:
                            encontrados += buscar_youtube(t, pais, max_res=15,
                                                          key=(cred or {}).get("YOUTUBE_API_KEY"))
                        diag.append(f"YouTube: {len(encontrados)} canales encontrados.")
                        res += encontrados
                    except Exception as e:
                        st.error(f"YouTube: {e}")
                if "Bluesky (datos oficiales)" in redes:
                    try:
                        encontrados = []
                        for t in terminos:
                            encontrados += buscar_bluesky(t, max_res=15)
                        diag.append(f"Bluesky: {len(encontrados)} perfiles encontrados.")
                        res += encontrados
                    except Exception as e:
                        st.error(f"Bluesky: {e}")
                redes_ia = [r for r in redes if r in SITIOS_IA]
                if redes_ia:
                    try:
                        encontrados = buscar_con_ia(client, modelos, marca_desc, sector, extra,
                                                    perfiles, redes_ia, rango, pais,
                                                    n=min(40, max(25, top + 10)), diag=diag)
                        diag.append(f"Agente IA ({', '.join(redes_ia)}): "
                                    f"{len(encontrados)} perfiles encontrados.")
                        res += encontrados
                    except Exception as e:
                        st.error(f"Agente IA: {e}")

            # Quitar duplicados entre fuentes
            unicos, vistos = [], set()
            for r in res:
                clave = r["url"].lower().rstrip("/")
                if clave not in vistos:
                    vistos.add(clave)
                    unicos.append(r)
            res = unicos

            # Verificar perfiles de Instagram con datos reales
            for r in res:
                r.setdefault("verificado", "")
                r.setdefault("interaccion", None)
            if instagram_conectado(cred):
                cuentas_ig = [r for r in res if usuario_instagram(r["url"])]
                if cuentas_ig:
                    verificadas = 0
                    with st.spinner(f"Revisando {len(cuentas_ig)} perfiles de Instagram..."):
                        for r in cuentas_ig:
                            try:
                                datos = verificar_instagram(usuario_instagram(r["url"]), cred)
                                r.update(seguidores=datos["seguidores"],
                                         interaccion=datos["interaccion"],
                                         contacto=r["contacto"] or datos["contacto"],
                                         descripcion=datos["bio"] or r["descripcion"],
                                         verificado="✅ real")
                                verificadas += 1
                            except Exception:
                                r["verificado"] = "⚠️ no verificable"
                    diag.append(f"Instagram: {verificadas} de {len(cuentas_ig)} perfiles "
                                "verificados con datos reales (el resto son cuentas personales "
                                "o el usuario no existe).")

            # Filtros, explicando cuántos se descartan
            minimo, maximo = RANGOS[rango]
            antes = len(res)
            res = [r for r in res
                   if (not r["seguidores"] and r["verificado"] != "✅ real")
                   or (r["red"].endswith("(IA)") and r["verificado"] != "✅ real")
                   or minimo <= r["seguidores"] <= maximo]
            if antes - len(res):
                diag.append(f"Filtro de tamaño ({rango}): {antes - len(res)} descartados.")
            if solo_contacto:
                antes = len(res)
                res = [r for r in res if r["contacto"]]
                if antes - len(res):
                    diag.append(f"Filtro «solo con contacto»: {antes - len(res)} descartados.")
            st.session_state.diagnostico = diag

            total = len(res)
            if res:
                with st.spinner(f"La IA está eligiendo los {top} mejores de {total}..."):
                    res = seleccionar_mejores(client, modelos, marca_desc, sector, rango, res, top)
                diag.append(f"Selección final: los {len(res)} mejores de {total} perfiles.")
            st.session_state.diagnostico = diag
            st.session_state.resultados = res

    # --- Resultados ---
    res = st.session_state.resultados
    diag = st.session_state.get("diagnostico")
    if diag:
        with st.expander(f"Cómo ha ido la búsqueda ({len(res)} candidatos)", expanded=not res):
            for linea in diag:
                st.write("• " + linea)
            if not res:
                st.warning("No ha quedado ningún candidato. Prueba a desmarcar «Solo cuentas con "
                           "contacto público visible», elegir un tamaño de audiencia más amplio o "
                           "usar palabras clave más concretas (ej.: «trading acciones España», "
                           "«análisis técnico bolsa»).")
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
                "interaccion": st.column_config.NumberColumn("Interacción %", format="%.2f"),
                "verificado": st.column_config.TextColumn("Datos"),
            },
            disabled=[c for c in df.columns if c != "guardar"],
            hide_index=True,
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
