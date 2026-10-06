# =====================================================================
# PublishFlow — Agencia de marketing (monolito multi-marca + automatización)
# =====================================================================
import os
import io
import re
import sys
import json
import time
import base64
import zipfile
import hashlib
import datetime as dt
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
import markdown as md
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

_DIR_APP = os.path.dirname(os.path.abspath(__file__))
if _DIR_APP not in sys.path:
    sys.path.insert(0, _DIR_APP)

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    _GENAI_DISPONIBLE = True
except Exception:
    genai = None
    types = None
    APIError = Exception
    _GENAI_DISPONIBLE = False


st.set_page_config(page_title="PublishFlow Agencia", page_icon="📣", layout="wide")

MODELOS_VALIDOS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]


# =====================================================================
# 1) MARCAS (hardcoded) + helpers de marcas personalizadas
# =====================================================================
MARCAS = {
    "AdeskCharts": {
        "descripcion": ("Plataforma web de trading con screener de acciones y agentes de IA que "
                        "analizan las acciones filtradas. Mejor servicio por menos dinero. "
                        "Suscripción de pago."),
        "url": "https://adeskcharts.com",
        "color": "#1E4FD8",
        "prefijo": "ADESK",
    },
    "SoundSnip Studio PRO": {
        "descripcion": ("Web de herramientas de audio: controlador DJ, mesa de estudio, efectos y "
                        "editor. Para DJs, productores y creadores. Suscripción de pago."),
        "url": "",
        "color": "#6D28D9",
        "prefijo": "SOUNDSNIP",
    },
    "PublishFlow": {
        "descripcion": ("Plataforma de agencia de marketing autónoma: campañas, publicación y "
                        "prospección de talento con IA. Para dueños de marcas y agencias."),
        "url": "",
        "color": "#0F766E",
        "prefijo": "PUBLISHFLOW",
    },
}


MARCAS_CUSTOM_PATH = os.path.join("data", "marcas_custom.json")


def _cargar_marcas_custom():
    if not os.path.exists(MARCAS_CUSTOM_PATH):
        return {}
    try:
        with open(MARCAS_CUSTOM_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _guardar_marcas_custom():
    try:
        os.makedirs("data", exist_ok=True)
        with open(MARCAS_CUSTOM_PATH, "w", encoding="utf-8") as f:
            json.dump(st.session_state.get("marcas_custom", {}), f,
                      ensure_ascii=False, indent=2)
    except OSError:
        pass


def marcas_todas():
    todas = dict(MARCAS)
    for nombre, datos in st.session_state.get("marcas_custom", {}).items():
        if nombre not in todas:
            todas[nombre] = datos
    return todas


def prefijo_desde_nombre(nombre):
    limpio = re.sub(r"[^A-Z0-9]", "", (nombre or "").upper())
    return limpio[:15] or "MARCA"


def marcas_buscador():
    return {nombre: datos.get("descripcion", "") for nombre, datos in marcas_todas().items()}


# =====================================================================
# 2) SECRETOS
# =====================================================================
def leer_secretos():
    planos = {}

    def recorrer(datos):
        for k, v in datos.items():
            if hasattr(v, "items") and not isinstance(v, str):
                recorrer(v)
            else:
                planos[str(k).strip().upper()] = v

    try:
        recorrer(st.secrets)
    except Exception as e:
        st.session_state["error_secrets"] = str(e)[:300]
    for k, v in os.environ.items():
        if k.upper() in ("GEMINI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY_PAGO"):
            planos.setdefault(k.upper(), v)
    return planos


SECRETOS_CRUDOS = leer_secretos()


def _separar_compartidos(secretos):
    prefijos = {datos["prefijo"] for datos in MARCAS.values()}
    compartidos = {}
    for k, v in secretos.items():
        k_up = str(k).strip().upper()
        if not any(k_up.startswith(p + "_") for p in prefijos):
            compartidos[k_up] = v
    return compartidos


SECRETOS = _separar_compartidos(SECRETOS_CRUDOS)
SECRETOS_POR_PREFIJO = {}


def cred_marca(marca):
    todas = marcas_todas()
    if marca not in todas:
        return dict(SECRETOS)
    prefijo = todas[marca]["prefijo"]
    resultado = dict(SECRETOS)
    for k, v in SECRETOS_CRUDOS.items():
        k_up = str(k).strip().upper()
        if k_up.startswith(prefijo + "_"):
            resultado[k_up[len(prefijo) + 1:]] = v
    resultado.update(st.session_state.cred_marcas.get(marca, {}))
    return resultado


# =====================================================================
# 3) IA EN CASCADA
# =====================================================================
PAUSA_AGOTADO = 10 * 60
CACHE_MODELOS = 60 * 60
MAX_MODELOS_POR_PROVEEDOR = 4

GEMINI_RESPALDO = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash",
                   "gemini-2.5-flash", "gemini-2.5-flash-lite"]
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_PREFERENCIA = ["llama-4-maverick", "llama-3.3-70b", "gpt-oss-120b", "kimi-k2", "qwen",
                    "llama-4-scout", "gpt-oss-20b", "llama-3.1-8b"]
GROQ_EXCLUIR = ("whisper", "tts", "guard", "playai", "orpheus", "distil", "safeguard")

ALIAS = {
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "API_KEY_GEMINI"],
    "groq": ["GROQ_API_KEY", "GROQ_KEY", "API_KEY_GROQ"],
    "pago": ["GEMINI_API_KEY_PAGO", "GEMINI_PAGO_API_KEY", "GEMINI_PAID_API_KEY",
             "GEMINI_API_KEY_3"],
}

_agotado_hasta = {}
_cache_modelos = {}
_ultimo_uso = {"proveedor": None, "modelo": None}
_ultimo_error = {}
_llamadas = {}
_modelos_sin_cuota = set()

PRIORIZAR_GROQ_EN_TAREAS_SIMPLES = True


def _espera_429(texto):
    m = re.search(r"retry in ([\d.]+)\s*s", texto, re.I) or \
        re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)", texto)
    segundos = float(m.group(1)) if m else 60.0
    if re.search(r"per ?day|PerDay|_per_day|daily", texto, re.I):
        return "diario", 3 * 60 * 60
    return "por minuto", min(segundos + 2, 300.0)


class Agotado(Exception):
    def __init__(self, mensaje, espera=PAUSA_AGOTADO):
        super().__init__(mensaje)
        self.espera = espera


class ClaveInvalida(Exception):
    pass


class SinBusquedaWeb(Exception):
    pass


def _limpiar(valor):
    return str(valor or "").strip().strip('"').strip("'")


def buscar_clave(secretos, tipo):
    for nombre in ALIAS[tipo]:
        valor = _limpiar(secretos.get(nombre))
        if valor:
            return valor
    for k, v in secretos.items():
        n = str(k).upper().replace("-", "_").replace(" ", "")
        valor = _limpiar(v)
        if not valor or "YOUTUBE" in n:
            continue
        de_pago = "PAGO" in n or "PAID" in n
        if tipo == "groq" and ("GROQ" in n or valor.startswith("gsk_")):
            return valor
        if tipo == "gemini" and not de_pago and ("GEMINI" in n or valor.startswith("AIza")):
            return valor
        if tipo == "pago" and de_pago and ("GEMINI" in n or valor.startswith("AIza")):
            return valor
    return ""


def _imagen_b64(img):
    img = img.convert("RGB")
    img.thumbnail((1024, 1024))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def _ordenar_gemini(nombres, preferir_pro):
    candidatos = []
    for n in nombres:
        n = n.split("/")[-1]
        if not n.startswith("gemini"):
            continue
        if any(x in n for x in ("tts", "image", "embedding", "live", "audio", "robotics",
                                "computer-use", "learnlm", "aqa", "nano", "veo")):
            continue
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        version = float(v.group(1)) if v else 0.0
        if "pro" in n:
            tipo = 0 if preferir_pro else 2
        elif "lite" in n:
            tipo = 2 if preferir_pro else 1
        elif "flash" in n:
            tipo = 1 if preferir_pro else 0
        else:
            tipo = 3
        preliminar = 1 if any(x in n for x in ("preview", "exp")) else 0
        candidatos.append((tipo, preliminar, -version, n))
    return [n for *_, n in sorted(set(candidatos))]


def modelos_gemini(client, clave, preferir_pro=False):
    llave = ("gemini", clave[-8:], preferir_pro)
    guardado = _cache_modelos.get(llave)
    if guardado and time.time() - guardado[0] < CACHE_MODELOS:
        return guardado[1]
    try:
        nombres = []
        for m in client.models.list():
            acciones = getattr(m, "supported_actions", None)
            if acciones and "generateContent" not in acciones:
                continue
            nombres.append(m.name)
        modelos = _ordenar_gemini(nombres, preferir_pro) or GEMINI_RESPALDO
    except Exception:
        modelos = GEMINI_RESPALDO
    _cache_modelos[llave] = (time.time(), modelos)
    return modelos


def modelos_groq(clave, buscar_web=False, con_imagen=False):
    llave = ("groq", clave[-8:])
    guardado = _cache_modelos.get(llave)
    if guardado and time.time() - guardado[0] < CACHE_MODELOS:
        ids = guardado[1]
    else:
        r = requests.get(f"{GROQ_URL}/models", headers={"Authorization": f"Bearer {clave}"},
                         timeout=20)
        if r.status_code == 401:
            raise ClaveInvalida("La clave de Groq no es válida.")
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
        _cache_modelos[llave] = (time.time(), ids)

    def puntuacion(mid):
        bajo = mid.lower()
        if buscar_web and "compound" in bajo:
            return (-2, 0)
        if con_imagen and "llama-4" in bajo:
            return (-1, 0)
        pos = next((i for i, p in enumerate(GROQ_PREFERENCIA) if p in bajo), 50)
        tam = re.search(r"(\d+)b", bajo)
        return (pos, -(int(tam.group(1)) if tam else 0))

    validos = [m for m in ids if not any(x in m.lower() for x in GROQ_EXCLUIR)
               and (buscar_web or "compound" not in m.lower())]
    return sorted(validos, key=puntuacion)


class GestorIA:
    def __init__(self, proveedores):
        self.proveedores = proveedores

    @classmethod
    def desde_secretos(cls, secretos):
        proveedores = []
        for nombre, tipo in (("Gemini gratis", "gemini"), ("Groq", "groq"),
                             ("Gemini de pago", "pago")):
            clave = buscar_clave(secretos, tipo)
            if clave:
                proveedores.append((nombre, tipo, clave))
        return cls(proveedores)

    def _gemini(self, clave, preferir_pro, prompt, imagenes, json_mode, buscar_web):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError("La librería google-genai no está instalada.")
        client = genai.Client(api_key=clave)
        args = {}
        if buscar_web:
            args["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        elif json_mode:
            args["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**args) if args else None
        contents = list(imagenes or []) + [prompt]

        cuota, ultimo = None, None
        modelos = [m for m in modelos_gemini(client, clave, preferir_pro)
                   if (clave[-8:], m) not in _modelos_sin_cuota]
        for modelo in modelos[:MAX_MODELOS_POR_PROVEEDOR]:
            for intento in range(2):
                try:
                    r = client.models.generate_content(model=modelo, contents=contents,
                                                       config=config)
                    if r and r.text:
                        return r.text, modelo
                    break
                except APIError as e:
                    ultimo, texto = e, str(e)
                    codigo = getattr(e, "code", None)
                    if codigo in (401, 403) or "API_KEY_INVALID" in texto:
                        raise ClaveInvalida("La clave de Gemini no es válida.")
                    if codigo == 429 or "RESOURCE_EXHAUSTED" in texto:
                        if "limit: 0" in texto:
                            _modelos_sin_cuota.add((clave[-8:], modelo))
                            break
                        tipo_limite, espera = _espera_429(texto)
                        if tipo_limite == "por minuto" and espera <= 25 and intento == 0:
                            time.sleep(espera)
                            continue
                        cuota = (f"límite {tipo_limite} de {modelo}", max(espera, 30.0))
                        break
                    if codigo in (500, 503) and intento == 0:
                        time.sleep(2)
                        continue
                    break
                except Exception as e:
                    ultimo = e
                    break
        if cuota:
            mensaje, espera = cuota
            raise Agotado(f"Gemini: {mensaje}", espera)
        raise RuntimeError(f"Gemini no respondió: {str(ultimo)[:300]}")

    def _groq(self, clave, prompt, imagenes, json_mode, buscar_web):
        cab = {"Authorization": f"Bearer {clave}"}
        cuota, ultimo = False, None
        modelos = modelos_groq(clave, buscar_web, bool(imagenes))
        if buscar_web:
            modelos = [m for m in modelos if "compound" in m.lower()]
            if not modelos:
                raise SinBusquedaWeb("Tu cuenta de Groq no tiene modelos con búsqueda en internet.")
        for modelo in modelos[:MAX_MODELOS_POR_PROVEEDOR]:
            contenido = prompt
            if imagenes and "llama-4" in modelo.lower():
                contenido = [{"type": "text", "text": prompt}] + [
                    {"type": "image_url", "image_url": {"url": _imagen_b64(img)}}
                    for img in imagenes[:3]]
            cuerpo = {"model": modelo, "messages": [{"role": "user", "content": contenido}],
                      "temperature": 0.7}
            if json_mode and "compound" not in modelo.lower():
                cuerpo["response_format"] = {"type": "json_object"}
            try:
                r = requests.post(f"{GROQ_URL}/chat/completions", headers=cab, json=cuerpo,
                                  timeout=180)
            except requests.RequestException as e:
                ultimo = e
                continue
            if r.status_code == 401:
                raise ClaveInvalida("La clave de Groq no es válida.")
            if r.status_code == 429:
                cuota = True
                continue
            if r.status_code >= 400:
                ultimo = f"{r.status_code}: {r.text[:200]}"
                continue
            texto = r.json()["choices"][0]["message"].get("content")
            if texto and buscar_web and re.search(
                    r"unable to (browse|access)|can.?t (browse|access)|no puedo (navegar|acceder|buscar)",
                    texto, re.I):
                ultimo = f"{modelo} no pudo buscar en internet"
                continue
            if texto:
                return texto, modelo
        if cuota:
            raise Agotado("Cuota de Groq agotada.")
        if buscar_web:
            raise SinBusquedaWeb(f"Groq no pudo buscar en internet: {ultimo}")
        raise RuntimeError(f"Groq no respondió: {ultimo}")

    def generar(self, prompt, imagenes=None, json_mode=False, buscar_web=False):
        if not self.proveedores:
            raise RuntimeError("No hay ninguna clave de IA configurada en los Secrets.")
        errores, sin_web = [], False
        proveedores = list(self.proveedores)
        if PRIORIZAR_GROQ_EN_TAREAS_SIMPLES and not buscar_web and not imagenes:
            proveedores.sort(key=lambda p: 0 if p[1] == "groq" else 1)
        for nombre, tipo, clave in proveedores:
            if _agotado_hasta.get(nombre, 0) > time.time():
                errores.append(f"{nombre}: en pausa por cuota agotada")
                continue
            try:
                if tipo == "groq":
                    texto, modelo = self._groq(clave, prompt, imagenes, json_mode, buscar_web)
                else:
                    texto, modelo = self._gemini(clave, tipo == "pago", prompt, imagenes,
                                                 json_mode, buscar_web)
                _ultimo_uso.update(proveedor=nombre, modelo=modelo)
                _llamadas[nombre] = _llamadas.get(nombre, 0) + 1
                _ultimo_error.pop(nombre, None)
                return texto
            except SinBusquedaWeb as e:
                errores.append(f"{nombre}: {e}")
                sin_web = True
            except Agotado as e:
                _agotado_hasta[nombre] = time.time() + getattr(e, "espera", PAUSA_AGOTADO)
                _ultimo_error[nombre] = str(e)
                errores.append(f"{nombre}: {e}")
            except Exception as e:
                _ultimo_error[nombre] = str(e)[:300]
                errores.append(f"{nombre}: {e}")
        if buscar_web and sin_web:
            raise SinBusquedaWeb(" | ".join(errores))
        raise RuntimeError("Ninguna IA pudo responder. " + " | ".join(errores))

    def estado(self):
        configurados = {n for n, _, _ in self.proveedores}
        filas = []
        for nombre in ("Gemini gratis", "Groq", "Gemini de pago"):
            if nombre not in configurados:
                filas.append((nombre, "⚪", "sin clave"))
            elif _agotado_hasta.get(nombre, 0) > time.time():
                minutos = int((_agotado_hasta[nombre] - time.time()) // 60) + 1
                motivo = _ultimo_error.get(nombre, "cuota agotada")
                filas.append((nombre, "🔴", f"{motivo}. Vuelve en {minutos} min"))
            elif _ultimo_error.get(nombre):
                filas.append((nombre, "🟠", f"falló: {_ultimo_error[nombre][:120]}"))
            elif _ultimo_uso["proveedor"] == nombre:
                filas.append((nombre, "🟢", f"en uso: {_ultimo_uso['modelo']}"))
            else:
                filas.append((nombre, "🟢", "lista"))
        return [(n, i, d + (f" · {_llamadas[n]} llamadas" if _llamadas.get(n) else ""))
                for n, i, d in filas]

    def diagnosticar(self):
        resultados = []
        for nombre, tipo, clave in self.proveedores:
            try:
                if tipo == "groq":
                    _, modelo = self._groq(clave, "Responde solo: OK", None, False, False)
                else:
                    client = genai.Client(api_key=clave)
                    disponibles = modelos_gemini(client, clave, tipo == "pago")
                    _, modelo = self._gemini(clave, tipo == "pago", "Responde solo: OK", None,
                                             False, False)
                    modelo = f"{modelo} (modelos vistos: {', '.join(disponibles[:6])})"
                _ultimo_error.pop(nombre, None)
                _agotado_hasta.pop(nombre, None)
                resultados.append((nombre, True, f"funciona con {modelo}"))
            except Exception as e:
                _ultimo_error[nombre] = str(e)[:300]
                resultados.append((nombre, False, str(e)[:400]))
        return resultados


def get_gemini_client():
    gestor = GestorIA.desde_secretos(SECRETOS)
    if not gestor.proveedores:
        nombres = ", ".join(sorted(SECRETOS)) or "ninguno"
        st.error("🔑 No encuentro ninguna clave de IA. En Secrets debe haber al menos "
                 "`GEMINI_API_KEY` o `GROQ_API_KEY`, escritas exactamente así.\n\n"
                 f"Nombres que veo ahora en tus Secrets: {nombres}")
        st.stop()
    return gestor


# =====================================================================
# 4) MOTOR (equipo, redes, conectores, Pillow)
# =====================================================================
EQUIPO = [
    {"id": "estrategia", "nombre": "Elena Navarro Ruiz", "rol": "Directora de Estrategia",
     "icono": "🧭", "bio": "Decide mercados, público, redes y horarios de cada campaña."},
    {"id": "copy", "nombre": "Marcos Vidal Herrera", "rol": "Copywriter Senior",
     "icono": "✍️", "bio": "Escribe los textos de cada red, los ganchos y los hashtags."},
    {"id": "creativa", "nombre": "Lucía Ortega Blanco", "rol": "Directora Creativa",
     "icono": "🎨", "bio": "Adapta tus imágenes a cada formato y escribe los guiones de vídeo."},
    {"id": "community", "nombre": "Daniel Soto Morales", "rol": "Community Manager",
     "icono": "📅", "bio": "Publica en las redes conectadas y prepara las descargas del resto."},
    {"id": "analista", "nombre": "Sara Méndez Castillo", "rol": "Analista de Resultados",
     "icono": "📈", "bio": "Sigue cada publicación y te dice qué funciona y qué no."},
    {"id": "talento", "nombre": "Javier Romero Gil", "rol": "Ojeador de Talento",
     "icono": "🤝", "bio": "Encuentra creadores y profesionales para colaborar con tus marcas."},
]
RETRATOS = {'estrategia': 'mujer española de unos 40 años, pelo castaño recogido, americana azul marino, sonrisa segura', 'copy': 'hombre español de unos 32 años, barba corta, jersey gris, gesto creativo y cercano', 'creativa': 'mujer española de unos 30 años, pelo ondulado oscuro, camisa negra, estilo creativo', 'community': 'hombre español de unos 27 años, pelo corto, camisa vaquera, sonrisa amable', 'analista': 'mujer española de unos 35 años, gafas finas, blusa blanca, expresión analítica y tranquila', 'talento': 'hombre español de unos 38 años, camiseta oscura y chaqueta informal, gesto sociable'}
for _m in EQUIPO:
    _m["retrato"] = RETRATOS[_m["id"]]
    _m["color"] = {'estrategia': '#C084FC', 'copy': '#22D3EE', 'creativa': '#F472B6', 'community': '#FBBF24', 'analista': '#34D399', 'talento': '#60A5FA'}[_m["id"]]
EQ = {m["id"]: m for m in EQUIPO}

ESTILO_RETRATO = (", retrato corporativo para la web de una agencia de marketing, fondo de oficina "
                  "moderna desenfocado con luces de neón moradas suaves, luz natural en la cara, "
                  "fotografía realista de alta calidad, encuadre de hombros hacia arriba, mirando a cámara")

MODELOS_IMAGEN = ["gemini-2.5-flash-image", "gemini-3-pro-image-preview", "imagen-4.0-generate-001"]

REDES = {
    "Telegram":       {"tamano": (1080, 1080), "limite": 1024, "tipo": "auto"},
    "Bluesky":        {"tamano": (1200, 675),  "limite": 300,  "tipo": "auto"},
    "Facebook":       {"tamano": (1080, 1350), "limite": 5000, "tipo": "auto"},
    "Instagram":      {"tamano": (1080, 1350), "limite": 2200, "tipo": "auto"},
    "Threads":        {"tamano": (1080, 1350), "limite": 500,  "tipo": "auto"},
    "LinkedIn":       {"tamano": (1200, 627),  "limite": 3000, "tipo": "auto"},
    "Pinterest":      {"tamano": (1000, 1500), "limite": 500,  "tipo": "auto"},
    "Discord":        {"tamano": (1200, 675),  "limite": 2000, "tipo": "auto"},
    "Mastodon":       {"tamano": (1200, 675),  "limite": 500,  "tipo": "auto"},
    "Blogger (Google)": {"tamano": (1200, 630), "limite": 60000, "tipo": "auto", "articulo": True},
    "WordPress":      {"tamano": (1200, 630),  "limite": 60000, "tipo": "auto", "articulo": True},
    "Dev.to":         {"tamano": (1000, 420),  "limite": 60000, "tipo": "auto", "articulo": True},
    "Newsletter (Brevo)": {"tamano": (1200, 630), "limite": 60000, "tipo": "auto", "articulo": True},
    "X (Twitter)":    {"tamano": (1600, 900),  "limite": 280,  "tipo": "manual",
                       "motivo": "Su API para publicar es de pago."},
    "TikTok":         {"tamano": (1080, 1920), "limite": 2200, "tipo": "manual",
                       "motivo": "Exige una auditoría de TikTok para publicar por API."},
    "YouTube Shorts": {"tamano": (1080, 1920), "limite": 5000, "tipo": "manual",
                       "motivo": "Publica vídeos y la agencia de momento entrega imagen y guion."},
    "WhatsApp":       {"tamano": (1080, 1080), "limite": 1000, "tipo": "manual",
                       "motivo": "Los canales de WhatsApp no tienen API."},
    "Reddit":         {"tamano": (1200, 675),  "limite": 3000, "tipo": "manual",
                       "motivo": "Sus comunidades castigan la autopromoción automática."},
    "Tumblr":         {"tamano": (1080, 1350), "limite": 2000, "tipo": "manual",
                       "motivo": "Su conexión es más compleja; se añadirá más adelante."},
    "Medium":         {"tamano": (1400, 788),  "limite": 60000, "tipo": "manual", "articulo": True,
                       "motivo": "Ya no da acceso nuevo a su API de publicación."},
    "Hashnode":       {"tamano": (1600, 840),  "limite": 60000, "tipo": "manual", "articulo": True,
                       "motivo": "Se añadirá más adelante."},
    "Perfil de Empresa de Google": {"tamano": (1200, 900), "limite": 1500, "tipo": "manual",
                       "motivo": "Su API requiere aprobación."},
}

TIPOS = {
    "auto": "Se publica directamente desde la app",
    "manual": "Descarga imagen y texto para subirlo a mano",
}


def _parse_json(texto):
    limpio = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        i, j = limpio.find("{"), limpio.rfind("}")
        if i != -1 and j != -1:
            return json.loads(limpio[i:j + 1])
        raise ValueError("La respuesta de la IA no tenía un formato válido.")


def llamar_ia(client, modelos, contents, json_mode=False, intentos=2):
    if hasattr(client, "generar"):
        partes = contents if isinstance(contents, list) else [contents]
        imagenes = [p for p in partes if isinstance(p, Image.Image)]
        texto = "\n".join(p for p in partes if isinstance(p, str))
        error = None
        for _ in range(intentos):
            respuesta = client.generar(texto, imagenes=imagenes, json_mode=json_mode)
            if not json_mode:
                return respuesta
            try:
                return _parse_json(respuesta)
            except (ValueError, json.JSONDecodeError) as e:
                error = e
        raise error
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    ultimo = None
    for modelo in modelos:
        for k in range(intentos):
            try:
                r = client.models.generate_content(model=modelo, contents=contents, config=config)
                if r and r.text:
                    return _parse_json(r.text) if json_mode else r.text
            except APIError as e:
                ultimo = e
                if getattr(e, "code", None) in (400, 404):
                    break
                time.sleep(2 * (k + 1))
            except (ValueError, json.JSONDecodeError) as e:
                ultimo = e
            except Exception as e:
                ultimo = e
                time.sleep(2 * (k + 1))
    raise ultimo or RuntimeError("No se obtuvo respuesta de la IA.")


def _brief_txt(b):
    return (f"MARCA: {b['marca']}\nPRODUCTO: {b['descripcion']}\nWEB: {b['url'] or '(sin web)'}\n"
            f"OBJETIVO: {b['objetivo']}\nMERCADO: {b['mercado']}\n"
            f"PÚBLICO INDICADO: {b['publico'] or '(decídelo tú)'}\n"
            f"OFERTA / LLAMADA A LA ACCIÓN: {b['oferta'] or '(ninguna concreta)'}")


def crear_estrategia(client, modelos, brief, redes, idioma, fotos_bytes=None):
    prompt = f"""
Eres {EQ['estrategia']['nombre']}, {EQ['estrategia']['rol']} de una agencia de marketing digital.
Analiza este encargo{" y las imágenes adjuntas" if fotos_bytes else ""}.

{_brief_txt(brief)}
REDES DE LA CAMPAÑA: {", ".join(redes)}
IDIOMA DE RESPUESTA: {idioma}

No inventes datos de la marca (precios, cifras, clientes). Horarios en hora local del mercado.

Devuelve SOLO JSON con esta estructura:
{{
 "resumen": "2-3 frases con tu visión de la campaña",
 "mensaje_clave": "la idea principal que debe transmitir toda la campaña",
 "publico": [{{"segmento": "", "descripcion": "", "motivacion": ""}}],
 "mercados": [{{"mercado": "", "motivo": ""}}],
 "redes": [{{"red": "nombre exacto de una red de la lista", "prioridad": "alta|media|baja",
            "motivo": "", "horarios": ["Martes 19:00"], "frecuencia": "3 por semana"}}],
 "plan_7_dias": [{{"dia": "Lunes", "red": "", "idea": "", "formato": ""}}],
 "nota_para_el_equipo": "indicaciones breves para el copywriter y la creativa"
}}
Incluye en "redes" TODAS las redes de la campaña.
"""
    contents = [Image.open(io.BytesIO(b)) for b in (fotos_bytes or [])[:3]] + [prompt]
    return llamar_ia(client, modelos, contents, json_mode=True)


def escribir_publicaciones(client, modelos, brief, estrategia, redes, idioma, tono):
    limites = ", ".join(f"{r} ({REDES[r]['limite']})" for r in redes)
    prompt = f"""
Eres {EQ['copy']['nombre']}, {EQ['copy']['rol']}. Escribe las publicaciones siguiendo la
estrategia de tu compañera Elena.

{_brief_txt(brief)}
ESTRATEGIA: {json.dumps(estrategia, ensure_ascii=False)}
TONO: {tono}
IDIOMA: {idioma}
REDES Y LÍMITE DE CARACTERES (incluyendo hashtags y enlace): {limites}

Reglas:
- Adapta el estilo a cada red.
- Escribe {{LINK}} donde deba ir el enlace, una sola vez por texto.
- La primera línea debe ser un gancho que haga parar el scroll.
- No inventes precios, cifras, opiniones ni testimonios.
- Entre 0 y 5 hashtags por red (ninguno en WhatsApp ni en artículos).
- En blogs y newsletter ({", ".join(r for r in redes if REDES[r].get("articulo")) or "ninguna"}) escribe
  un artículo de 300 a 500 palabras en Markdown, con subtítulos, que aporte valor real.
- Cada publicación lleva un "titulo".

Devuelve SOLO JSON:
{{
 "gancho_imagen": "frase de máximo 7 palabras",
 "publicaciones": {{
   "NombreExactoDeLaRed": {{"titulo": "", "texto": "", "variante_b": "", "hashtags": ["#ejemplo"]}}
 }}
}}
Incluye TODAS las redes de la lista.
"""
    return llamar_ia(client, modelos, prompt, json_mode=True)


def escribir_guion(client, modelos, brief, estrategia, idioma, tono):
    prompt = f"""
Eres {EQ['creativa']['nombre']}, {EQ['creativa']['rol']}. Escribe un guion de vídeo vertical de
unos 30 segundos (Reels, TikTok, YouTube Shorts) para esta campaña.
Se grabará con las imágenes o vídeos del producto que suba el cliente y textos en pantalla.

{_brief_txt(brief)}
MENSAJE CLAVE: {estrategia.get('mensaje_clave', '')}
TONO: {tono}
IDIOMA: {idioma}

Estructura en Markdown:
### Gancho (0-3 s)
### Desarrollo
Tabla con columnas: Segundos | Qué se ve | Texto en pantalla | Voz en off
### Cierre y llamada a la acción
### Música
Estilo recomendado. Indica que debe ser música libre de derechos.
"""
    return llamar_ia(client, modelos, prompt)


def informe_resultados(client, modelos, brief, metricas, idioma):
    prompt = f"""
Eres {EQ['analista']['nombre']}, {EQ['analista']['rol']}. Escribe un informe breve y claro
para el cliente a partir de estas métricas de la campaña.

{_brief_txt(brief)}
MÉTRICAS POR RED: {json.dumps(metricas, ensure_ascii=False)}
IDIOMA: {idioma}

Estructura en Markdown:
### Resumen en una frase
### Qué ha funcionado
### Qué no ha funcionado
### Próximos pasos (3 acciones concretas)
Basa todo en los datos. Si faltan datos para concluir algo, dilo.
"""
    return llamar_ia(client, modelos, prompt)


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "campana"


def enlace_utm(url, red, campana):
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={slug(red)}&utm_medium=social&utm_campaign={slug(campana)}"


def texto_final(pub, link, red):
    base = (pub.get("texto") or "").strip()
    if link:
        base = base.replace("{LINK}", link) if "{LINK}" in base else f"{base}\n\n{link}"
    else:
        base = base.replace("{LINK}", "").strip()

    if REDES[red].get("articulo"):
        base = (pub.get("texto") or "").strip()
        if link:
            base = (base.replace("{LINK}", link) if "{LINK}" in base
                    else f"{base}\n\n[Más información]({link})")
        return base.replace("{LINK}", "").strip()

    tags = [h if h.startswith("#") else f"#{h}" for h in (pub.get("hashtags") or []) if h]
    limite = REDES[red]["limite"]

    while tags and len(base) + 2 + len(" ".join(tags)) > limite:
        tags.pop()
    final = f"{base}\n\n{' '.join(tags)}" if tags else base

    if len(final) > limite:
        recorte = limite - 1
        if link and link in final and len(link) < limite - 10:
            cuerpo = final.replace(link, "").strip()
            final = cuerpo[: recorte - len(link) - 2].rstrip() + "…\n\n" + link
        else:
            final = final[:recorte].rstrip() + "…"
    return final


def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(tamano):
    for nombre in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:
        return ImageFont.load_default()


def _ajustar(draw, texto, fuente, ancho_max, max_lineas=3):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas[:max_lineas]


def crear_pieza(foto_bytes, tamano, color, gancho, logo_bytes=None):
    w, h = tamano
    rgb = _hex_rgb(color)
    claro = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) > 160
    color_texto = (20, 20, 20) if claro else (255, 255, 255)
    if foto_bytes:
        img = ImageOps.fit(Image.open(io.BytesIO(foto_bytes)).convert("RGB"), tamano,
                           Image.Resampling.LANCZOS)
        banda = int(h * 0.18)
        zona = (0, h - banda, w, h)
    else:
        img = Image.new("RGB", tamano, rgb)
        zona = (0, 0, w, h)
    draw = ImageDraw.Draw(img, "RGBA")
    if foto_bytes:
        draw.rectangle(zona, fill=(*rgb, 232))
    if gancho:
        alto_zona = zona[3] - zona[1]
        tam = int(min(alto_zona * (0.28 if foto_bytes else 0.09), w * 0.075))
        fuente = _fuente(max(tam, 18))
        lineas = _ajustar(draw, gancho, fuente, w * 0.88)
        alto_linea = int(fuente.size * 1.2) if hasattr(fuente, "size") else 20
        y = zona[1] + (alto_zona - alto_linea * len(lineas)) // 2
        for linea in lineas:
            ancho = draw.textlength(linea, font=fuente)
            draw.text(((w - ancho) / 2, y), linea, font=fuente, fill=color_texto)
            y += alto_linea
    if logo_bytes:
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        logo.thumbnail((int(w * 0.2), int(h * 0.1)))
        img.paste(logo, (int(w * 0.04), int(h * 0.04)), logo)
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=88)
    return salida.getvalue()


def _comprimir(imagen, max_bytes=950_000):
    if len(imagen) <= max_bytes:
        return imagen
    img = Image.open(io.BytesIO(imagen)).convert("RGB")
    for calidad in (80, 70, 60, 50, 40):
        out = io.BytesIO()
        img.save(out, "JPEG", quality=calidad)
        if out.tell() <= max_bytes:
            return out.getvalue()
    img.thumbnail((1000, 1000))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=60)
    return out.getvalue()


def _ok(r, nombre):
    if r.status_code >= 400:
        raise RuntimeError(f"{nombre} respondió {r.status_code}: {r.text[:300]}")
    return r


def _html(texto):
    return md.markdown(texto or "", extensions=["extra"])


def _primer_enlace(texto):
    m = re.search(r"https?://\S+", texto or "")
    return m.group().rstrip(").,") if m else ""


def _telegram_probar(c):
    r = requests.get(f"https://api.telegram.org/bot{c['TELEGRAM_BOT_TOKEN']}/getChat",
                     params={"chat_id": c["TELEGRAM_CHAT_ID"]}, timeout=20).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description", "Token o canal incorrectos."))
    return f"Canal: {r['result'].get('title', c['TELEGRAM_CHAT_ID'])}"


def _telegram(texto, titulo, imagen, c):
    datos = requests.post(
        f"https://api.telegram.org/bot{c['TELEGRAM_BOT_TOKEN']}/sendPhoto",
        data={"chat_id": c["TELEGRAM_CHAT_ID"], "caption": texto[:1024]},
        files={"photo": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60).json()
    if not datos.get("ok"):
        raise RuntimeError(datos.get("description", "Telegram rechazó la publicación."))
    chat = str(c["TELEGRAM_CHAT_ID"])
    msg_id = datos["result"]["message_id"]
    return f"https://t.me/{chat[1:]}/{msg_id}" if chat.startswith("@") else "Publicado en Telegram"


def _bsky_sesion(c):
    r = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                      json={"identifier": c["BLUESKY_HANDLE"],
                            "password": c["BLUESKY_APP_PASSWORD"]}, timeout=30)
    return _ok(r, "Bluesky").json()


def _bluesky_probar(c):
    return f"Cuenta: @{_bsky_sesion(c)['handle']}"


def _bluesky(texto, titulo, imagen, c):
    base = "https://bsky.social/xrpc/"
    sesion = _bsky_sesion(c)
    cab = {"Authorization": f"Bearer {sesion['accessJwt']}"}
    blob = _ok(requests.post(base + "com.atproto.repo.uploadBlob",
                             headers={**cab, "Content-Type": "image/jpeg"},
                             data=_comprimir(imagen), timeout=60), "Bluesky")
    texto = texto if len(texto) <= 300 else texto[:299] + "…"
    registro = {
        "$type": "app.bsky.feed.post", "text": texto,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images",
                  "images": [{"alt": texto[:200], "image": blob.json()["blob"]}]},
    }
    facetas = []
    for m in re.finditer(r"https?://\S+", texto):
        inicio = len(texto[:m.start()].encode("utf-8"))
        facetas.append({"index": {"byteStart": inicio,
                                  "byteEnd": inicio + len(m.group().encode("utf-8"))},
                        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}]})
    if facetas:
        registro["facets"] = facetas
    r = _ok(requests.post(base + "com.atproto.repo.createRecord", headers=cab,
                          json={"repo": sesion["did"], "collection": "app.bsky.feed.post",
                                "record": registro}, timeout=30), "Bluesky")
    return f"https://bsky.app/profile/{sesion['handle']}/post/{r.json()['uri'].split('/')[-1]}"


def _graph(c):
    return f"https://graph.facebook.com/{c.get('FB_GRAPH_VERSION') or 'v23.0'}"


def _facebook_probar(c):
    r = _ok(requests.get(f"{_graph(c)}/{c['FB_PAGE_ID']}",
                         params={"fields": "name", "access_token": c["FB_PAGE_TOKEN"]},
                         timeout=20), "Facebook").json()
    return f"Página: {r.get('name')}"


def _facebook(texto, titulo, imagen, c):
    datos = _ok(requests.post(f"{_graph(c)}/{c['FB_PAGE_ID']}/photos",
                              data={"message": texto, "access_token": c["FB_PAGE_TOKEN"]},
                              files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                              timeout=60), "Facebook").json()
    return f"https://www.facebook.com/{datos.get('post_id', datos.get('id'))}"


def _alojar_imagen(imagen, c):
    foto = _ok(requests.post(f"{_graph(c)}/{c['FB_PAGE_ID']}/photos",
                             data={"published": "false", "access_token": c["FB_PAGE_TOKEN"]},
                             files={"source": ("pieza.jpg", imagen, "image/jpeg")},
                             timeout=60), "Facebook").json()
    info = _ok(requests.get(f"{_graph(c)}/{foto['id']}",
                            params={"fields": "images", "access_token": c["FB_PAGE_TOKEN"]},
                            timeout=20), "Facebook").json()
    return info["images"][0]["source"]


def _instagram_probar(c):
    r = _ok(requests.get(f"{_graph(c)}/{c['IG_USER_ID']}",
                         params={"fields": "username", "access_token": c["FB_PAGE_TOKEN"]},
                         timeout=20), "Instagram").json()
    return f"Cuenta: @{r.get('username')}"


def _instagram(texto, titulo, imagen, c):
    g, tok, ig = _graph(c), c["FB_PAGE_TOKEN"], c["IG_USER_ID"]
    cont = _ok(requests.post(f"{g}/{ig}/media", data={"image_url": _alojar_imagen(imagen, c),
                                                       "caption": texto, "access_token": tok},
                             timeout=60), "Instagram").json()["id"]
    for _ in range(15):
        estado = requests.get(f"{g}/{cont}", params={"fields": "status_code",
                                                      "access_token": tok}, timeout=20).json()
        if estado.get("status_code") == "FINISHED":
            break
        if estado.get("status_code") == "ERROR":
            raise RuntimeError("Instagram no pudo procesar la imagen.")
        time.sleep(2)
    pub = _ok(requests.post(f"{g}/{ig}/media_publish",
                            data={"creation_id": cont, "access_token": tok}, timeout=60),
              "Instagram").json()
    enlace = requests.get(f"{g}/{pub['id']}", params={"fields": "permalink",
                                                       "access_token": tok}, timeout=20).json()
    return enlace.get("permalink", "Publicado en Instagram")


def _threads_probar(c):
    r = _ok(requests.get("https://graph.threads.net/v1.0/me",
                         params={"fields": "username", "access_token": c["THREADS_TOKEN"]},
                         timeout=20), "Threads").json()
    return f"Cuenta: @{r.get('username')}"


def _threads(texto, titulo, imagen, c):
    base, tok, uid = "https://graph.threads.net/v1.0", c["THREADS_TOKEN"], c["THREADS_USER_ID"]
    cont = _ok(requests.post(f"{base}/{uid}/threads",
                             data={"media_type": "IMAGE", "image_url": _alojar_imagen(imagen, c),
                                   "text": texto[:500], "access_token": tok}, timeout=60),
               "Threads").json()["id"]
    for _ in range(15):
        estado = requests.get(f"{base}/{cont}", params={"fields": "status",
                                                         "access_token": tok}, timeout=20).json()
        if estado.get("status") == "FINISHED":
            break
        if estado.get("status") == "ERROR":
            raise RuntimeError("Threads no pudo procesar la imagen.")
        time.sleep(2)
    _ok(requests.post(f"{base}/{uid}/threads_publish",
                      data={"creation_id": cont, "access_token": tok}, timeout=60), "Threads")
    return "Publicado en Threads"


def _li_cab(c):
    version = c.get("LINKEDIN_VERSION") or (dt.date.today().replace(day=1)
                                             - dt.timedelta(days=60)).strftime("%Y%m")
    return {"Authorization": f"Bearer {c['LINKEDIN_TOKEN']}", "LinkedIn-Version": version,
            "X-Restli-Protocol-Version": "2.0.0"}


def _li_autor(c):
    if c.get("LINKEDIN_URN"):
        return c["LINKEDIN_URN"], "página indicada"
    r = _ok(requests.get("https://api.linkedin.com/v2/userinfo",
                         headers={"Authorization": f"Bearer {c['LINKEDIN_TOKEN']}"}, timeout=20),
            "LinkedIn").json()
    return f"urn:li:person:{r['sub']}", r.get("name", "")


def _linkedin_probar(c):
    return f"Publicará como: {_li_autor(c)[1]}"


def _linkedin(texto, titulo, imagen, c):
    autor, _ = _li_autor(c)
    cab = _li_cab(c)
    ini = _ok(requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                            headers=cab, json={"initializeUploadRequest": {"owner": autor}},
                            timeout=30), "LinkedIn").json()["value"]
    _ok(requests.put(ini["uploadUrl"], data=imagen,
                     headers={"Authorization": cab["Authorization"]}, timeout=60), "LinkedIn")
    r = _ok(requests.post("https://api.linkedin.com/rest/posts", headers=cab, json={
        "author": autor, "commentary": texto, "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "content": {"media": {"id": ini["image"], "altText": titulo or texto[:100]}},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False,
    }, timeout=30), "LinkedIn")
    urn = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{urn}" if urn else "Publicado en LinkedIn"


def _pinterest_probar(c):
    cab = {"Authorization": f"Bearer {c['PINTEREST_TOKEN']}"}
    yo = _ok(requests.get("https://api.pinterest.com/v5/user_account", headers=cab, timeout=20),
             "Pinterest").json()
    tableros = requests.get("https://api.pinterest.com/v5/boards", headers=cab,
                            timeout=20).json().get("items", [])
    lista = "; ".join(f"{t['name']} → {t['id']}" for t in tableros[:15])
    aviso = "" if c.get("PINTEREST_BOARD_ID") else " Copia el ID del tablero."
    return f"Cuenta: {yo.get('username')}. Tableros: {lista or 'ninguno'}.{aviso}"


def _pinterest(texto, titulo, imagen, c):
    if not c.get("PINTEREST_BOARD_ID"):
        raise RuntimeError("Falta el ID del tablero.")
    cuerpo = {"board_id": c["PINTEREST_BOARD_ID"], "title": (titulo or texto)[:100],
              "description": texto[:500],
              "media_source": {"source_type": "image_base64", "content_type": "image/jpeg",
                               "data": base64.b64encode(imagen).decode()}}
    enlace = _primer_enlace(texto)
    if enlace:
        cuerpo["link"] = enlace
    r = _ok(requests.post("https://api.pinterest.com/v5/pins", json=cuerpo, timeout=60,
                          headers={"Authorization": f"Bearer {c['PINTEREST_TOKEN']}"}),
            "Pinterest").json()
    return f"https://www.pinterest.com/pin/{r['id']}/"


def _discord_probar(c):
    r = _ok(requests.get(c["DISCORD_WEBHOOK_URL"], timeout=20), "Discord").json()
    return f"Webhook: {r.get('name')}"


def _discord(texto, titulo, imagen, c):
    _ok(requests.post(c["DISCORD_WEBHOOK_URL"], params={"wait": "true"},
                      data={"payload_json": json.dumps({"content": texto[:2000]})},
                      files={"files[0]": ("pieza.jpg", imagen, "image/jpeg")}, timeout=60),
        "Discord")
    return "Publicado en Discord"


def _masto(c):
    return c["MASTODON_URL"].rstrip("/"), {"Authorization": f"Bearer {c['MASTODON_TOKEN']}"}


def _mastodon_probar(c):
    base, cab = _masto(c)
    r = _ok(requests.get(f"{base}/api/v1/accounts/verify_credentials", headers=cab, timeout=20),
            "Mastodon").json()
    return f"Cuenta: @{r.get('acct')}"


def _mastodon(texto, titulo, imagen, c):
    base, cab = _masto(c)
    media = _ok(requests.post(f"{base}/api/v2/media", headers=cab,
                              files={"file": ("pieza.jpg", imagen, "image/jpeg")},
                              data={"description": (titulo or texto)[:200]}, timeout=60),
                "Mastodon").json()
    for _ in range(10):
        if media.get("url"):
            break
        time.sleep(2)
        media = requests.get(f"{base}/api/v1/media/{media['id']}", headers=cab, timeout=20).json()
    r = _ok(requests.post(f"{base}/api/v1/statuses", headers=cab,
                          data={"status": texto[:500], "media_ids[]": media["id"]}, timeout=30),
            "Mastodon").json()
    return r.get("url", "Publicado en Mastodon")


def _google_token(c):
    r = _ok(requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": c["BLOGGER_CLIENT_ID"], "client_secret": c["BLOGGER_CLIENT_SECRET"],
        "refresh_token": c["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"},
        timeout=20), "Google").json()
    return r["access_token"]


def _blogger_probar(c):
    r = _ok(requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{c['BLOGGER_BLOG_ID']}",
                         headers={"Authorization": f"Bearer {_google_token(c)}"}, timeout=20),
            "Blogger").json()
    return f"Blog: {r.get('name')}"


def _blogger(texto, titulo, imagen, c):
    r = _ok(requests.post(
        f"https://www.googleapis.com/blogger/v3/blogs/{c['BLOGGER_BLOG_ID']}/posts/",
        headers={"Authorization": f"Bearer {_google_token(c)}"},
        json={"title": titulo or "Novedades", "content": _html(texto)}, timeout=30),
        "Blogger").json()
    return r.get("url", "Publicado en Blogger")


def _wp(c):
    return c["WP_URL"].rstrip("/") + "/wp-json/wp/v2", (c["WP_USER"], c["WP_APP_PASSWORD"])


def _wordpress_probar(c):
    base, auth = _wp(c)
    r = _ok(requests.get(f"{base}/users/me", auth=auth, timeout=20), "WordPress").json()
    return f"Usuario: {r.get('name')}"


def _wordpress(texto, titulo, imagen, c):
    base, auth = _wp(c)
    media = _ok(requests.post(f"{base}/media", auth=auth, data=imagen, timeout=60, headers={
        "Content-Disposition": 'attachment; filename="pieza.jpg"', "Content-Type": "image/jpeg"}),
        "WordPress").json()
    r = _ok(requests.post(f"{base}/posts", auth=auth, timeout=30, json={
        "title": titulo or "Novedades", "content": _html(texto), "status": "publish",
        "featured_media": media["id"]}), "WordPress").json()
    return r.get("link", "Publicado en WordPress")


def _devto_probar(c):
    r = _ok(requests.get("https://dev.to/api/users/me", headers={"api-key": c["DEVTO_API_KEY"]},
                         timeout=20), "Dev.to").json()
    return f"Cuenta: @{r.get('username')}"


def _devto(texto, titulo, imagen, c, etiquetas=()):
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in etiquetas][:4]
    r = _ok(requests.post("https://dev.to/api/articles", headers={"api-key": c["DEVTO_API_KEY"]},
                          json={"article": {"title": titulo or "Novedades", "body_markdown": texto,
                                            "published": True, "tags": [t for t in tags if t]}},
                          timeout=30), "Dev.to").json()
    return r.get("url", "Publicado en Dev.to")


def _brevo_probar(c):
    r = _ok(requests.get("https://api.brevo.com/v3/account", headers={"api-key": c["BREVO_API_KEY"]},
                         timeout=20), "Brevo").json()
    return f"Cuenta: {r.get('email')}"


def _brevo(texto, titulo, imagen, c):
    cab = {"api-key": c["BREVO_API_KEY"]}
    camp = _ok(requests.post("https://api.brevo.com/v3/emailCampaigns", headers=cab, json={
        "name": f"PublishFlow {dt.datetime.now():%Y-%m-%d %H:%M}",
        "subject": titulo or "Novedades",
        "sender": {"name": c["BREVO_SENDER_NAME"], "email": c["BREVO_SENDER_EMAIL"]},
        "type": "classic", "htmlContent": _html(texto),
        "recipients": {"listIds": [int(c["BREVO_LIST_ID"])]}}, timeout=30), "Brevo").json()
    _ok(requests.post(f"https://api.brevo.com/v3/emailCampaigns/{camp['id']}/sendNow",
                      headers=cab, timeout=30), "Brevo")
    return "Newsletter enviada"


def _campo(clave, etiqueta, secreto=False, ayuda=None, opcional=False):
    return {"clave": clave, "etiqueta": etiqueta, "secreto": secreto, "ayuda": ayuda,
            "opcional": opcional}


CONECTORES = {
    "Telegram": {
        "campos": [_campo("TELEGRAM_BOT_TOKEN", "Token del bot", True),
                   _campo("TELEGRAM_CHAT_ID", "Canal", ayuda="Ej.: @tucanal")],
        "pasos": "1. En Telegram, abre **@BotFather**, escribe `/newbot` y copia el token.\n"
                 "2. Añade el bot como **administrador** de tu canal.\n"
                 "3. Si el canal es público, su ID es su @nombre.",
        "probar": _telegram_probar, "publicar": _telegram},
    "Bluesky": {
        "campos": [_campo("BLUESKY_HANDLE", "Usuario", ayuda="Ej.: tunombre.bsky.social"),
                   _campo("BLUESKY_APP_PASSWORD", "Contraseña de app", True)],
        "pasos": "1. En Bluesky: **Ajustes → Privacidad y seguridad → Contraseñas de app**.\n"
                 "2. Crea una nueva y cópiala.",
        "probar": _bluesky_probar, "publicar": _bluesky},
    "Facebook": {
        "campos": [_campo("FB_PAGE_ID", "ID de la página"),
                   _campo("FB_PAGE_TOKEN", "Token de la página", True),
                   _campo("FB_GRAPH_VERSION", "Versión de la API", opcional=True)],
        "pasos": "1. Crea una app en **developers.facebook.com**.\n"
                 "2. Pide permisos `pages_manage_posts`, `pages_read_engagement`.\n"
                 "3. Genera un token de página de larga duración.",
        "probar": _facebook_probar, "publicar": _facebook},
    "Instagram": {
        "campos": [_campo("IG_USER_ID", "ID de la cuenta de Instagram",
                          ayuda="Usa el mismo token que Facebook")],
        "requiere": ["Facebook"],
        "pasos": "1. Instagram profesional vinculado a página de Facebook.\n"
                 "2. Conecta primero Facebook.\n"
                 "3. Consulta `TU_ID_DE_PAGINA?fields=instagram_business_account`.",
        "probar": _instagram_probar, "publicar": _instagram},
    "Threads": {
        "campos": [_campo("THREADS_USER_ID", "ID de usuario de Threads"),
                   _campo("THREADS_TOKEN", "Token de Threads", True)],
        "requiere": ["Facebook"],
        "pasos": "1. En tu app de Meta añade el caso de uso Threads API.\n"
                 "2. Genera un token.",
        "probar": _threads_probar, "publicar": _threads},
    "LinkedIn": {
        "campos": [_campo("LINKEDIN_TOKEN", "Token de acceso", True),
                   _campo("LINKEDIN_URN", "URN de página de empresa", opcional=True),
                   _campo("LINKEDIN_VERSION", "Versión de la API", opcional=True)],
        "pasos": "1. Crea una app en **linkedin.com/developers**.\n"
                 "2. En Token Generator crea un token con `openid`, `profile` y `w_member_social`.",
        "probar": _linkedin_probar, "publicar": _linkedin},
    "Pinterest": {
        "campos": [_campo("PINTEREST_TOKEN", "Token de acceso", True),
                   _campo("PINTEREST_BOARD_ID", "ID del tablero", opcional=True)],
        "pasos": "1. Crea una app en **developers.pinterest.com**.\n"
                 "2. Genera un token con `boards:read`, `pins:read` y `pins:write`.",
        "probar": _pinterest_probar, "publicar": _pinterest},
    "Discord": {
        "campos": [_campo("DISCORD_WEBHOOK_URL", "URL del webhook", True)],
        "pasos": "1. En tu servidor: Editar canal → Integraciones → Webhooks → Nuevo webhook.\n"
                 "2. Copia la URL.",
        "probar": _discord_probar, "publicar": _discord},
    "Mastodon": {
        "campos": [_campo("MASTODON_URL", "Servidor", ayuda="Ej.: https://mastodon.social"),
                   _campo("MASTODON_TOKEN", "Token de acceso", True)],
        "pasos": "1. En Mastodon: Preferencias → Desarrollo → Nueva aplicación.\n"
                 "2. Marca `read:accounts`, `write:statuses` y `write:media`.",
        "probar": _mastodon_probar, "publicar": _mastodon},
    "Blogger (Google)": {
        "campos": [_campo("BLOGGER_BLOG_ID", "ID del blog"),
                   _campo("BLOGGER_CLIENT_ID", "Client ID de Google"),
                   _campo("BLOGGER_CLIENT_SECRET", "Client secret de Google", True),
                   _campo("BLOGGER_REFRESH_TOKEN", "Refresh token", True)],
        "pasos": "1. En **console.cloud.google.com** activa Blogger API v3.\n"
                 "2. Crea credenciales OAuth con redirección "
                 "`https://developers.google.com/oauthplayground`.",
        "probar": _blogger_probar, "publicar": _blogger},
    "WordPress": {
        "campos": [_campo("WP_URL", "Dirección de tu web"),
                   _campo("WP_USER", "Usuario"),
                   _campo("WP_APP_PASSWORD", "Contraseña de aplicación", True)],
        "pasos": "1. En tu WordPress: Usuarios → Perfil → Contraseñas de aplicación.\n"
                 "2. Crea una y cópiala.",
        "probar": _wordpress_probar, "publicar": _wordpress},
    "Dev.to": {
        "campos": [_campo("DEVTO_API_KEY", "Clave de API", True)],
        "pasos": "1. En dev.to: Settings → Extensions → DEV Community API Keys.",
        "probar": _devto_probar, "publicar": _devto},
    "Newsletter (Brevo)": {
        "campos": [_campo("BREVO_API_KEY", "Clave de API", True),
                   _campo("BREVO_SENDER_NAME", "Nombre del remitente"),
                   _campo("BREVO_SENDER_EMAIL", "Email del remitente"),
                   _campo("BREVO_LIST_ID", "ID de la lista")],
        "pasos": "1. En Brevo: Ajustes → SMTP y API → Claves API → Generar.\n"
                 "2. Verifica tu email de remitente.\n"
                 "3. El ID de la lista está en Contactos → Listas.",
        "probar": _brevo_probar, "publicar": _brevo},
}


def campos_obligatorios(red):
    return [c["clave"] for c in CONECTORES.get(red, {}).get("campos", []) if not c["opcional"]]


def conectado(red, cred):
    spec = CONECTORES.get(red)
    if not spec:
        return False
    if not all(cred.get(k) for k in campos_obligatorios(red)):
        return False
    return all(conectado(dep, cred) for dep in spec.get("requiere", []))


def probar(red, cred):
    spec = CONECTORES[red]
    faltan = [c["etiqueta"] for c in spec["campos"] if not c["opcional"] and not cred.get(c["clave"])]
    if faltan:
        raise RuntimeError("Faltan datos: " + ", ".join(faltan))
    for dep in spec.get("requiere", []):
        if not conectado(dep, cred):
            raise RuntimeError(f"Conecta primero {dep}.")
    return spec["probar"](cred)


def publicar(red, texto, titulo, imagen, cred, etiquetas=()):
    if not conectado(red, cred):
        raise RuntimeError(f"{red} no está conectado. Ve a la pestaña Conexiones.")
    if red == "Dev.to":
        return _devto(texto, titulo, imagen, cred, etiquetas)
    return CONECTORES[red]["publicar"](texto, titulo, imagen, cred)


def claves_de(red):
    return [c["clave"] for c in CONECTORES.get(red, {}).get("campos", [])]


def secrets_toml(cred, prefijo=""):
    claves = [c["clave"] for spec in CONECTORES.values() for c in spec["campos"]]
    lineas = []
    for k in claves:
        if cred.get(k):
            nombre = f"{prefijo}_{k}" if prefijo else k
            lineas.append(f'{nombre} = {json.dumps(str(cred[k]))}')
    return "\n".join(lineas)


def pack_zip(redes, piezas, textos, guion, estrategia):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for red in redes:
            carpeta = re.sub(r"[^\w]+", "_", red).strip("_")
            z.writestr(f"{carpeta}/imagen.jpg", piezas[red])
            z.writestr(f"{carpeta}/texto.txt", textos[red])
        z.writestr("guion_video.md", guion or "")
        z.writestr("estrategia.json", json.dumps(estrategia, ensure_ascii=False, indent=2))
    return buffer.getvalue()


def recortar_retrato(datos, lado=512):
    img = ImageOps.fit(Image.open(io.BytesIO(datos)).convert("RGB"), (lado, lado),
                       Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def generar_retrato(client, miembro, modelos=None):
    prompt = "Fotografía de " + miembro["retrato"] + ESTILO_RETRATO
    ultimo = None
    for modelo in modelos or MODELOS_IMAGEN:
        try:
            if modelo.startswith("imagen"):
                r = client.models.generate_images(
                    model=modelo, prompt=prompt,
                    config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"))
                datos = r.generated_images[0].image.image_bytes
            else:
                r = client.models.generate_content(
                    model=modelo, contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
                datos = next((p.inline_data.data for p in r.candidates[0].content.parts
                              if getattr(p, "inline_data", None) and p.inline_data.data), None)
            if datos:
                return recortar_retrato(datos)
        except Exception as e:
            ultimo = e
    raise ultimo or RuntimeError("Ningún modelo de imagen devolvió una foto.")


def zip_fotos(fotos):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for id_miembro, datos in fotos.items():
            z.writestr(f"fotos/{id_miembro}.jpg", datos)
    return buffer.getvalue()


# =====================================================================
# 5) ALMACÉN DE TALENTOS + PROGRAMACIÓN
# =====================================================================
DATA_DIR = "data"
CACHE_PATH = os.path.join(DATA_DIR, "talentos_cache.json")
RESULT_PATH = os.path.join(DATA_DIR, "talentos_resultados.json")
HIST_PATH = os.path.join(DATA_DIR, "talentos_historial.json")
PLAN_AUTO_PATH = os.path.join(DATA_DIR, "plan_publicacion.json")
REGISTRO_AUTO_PATH = os.path.join(DATA_DIR, "registro_auto.json")
PIEZAS_DIR = os.path.join(DATA_DIR, "piezas")

TTL_HORAS_DEFECTO = 168
ESTADOS_CONTACTO = ["pendiente", "contactado", "respondido", "cerrado", "descartado"]


def _leer_json(path, defecto):
    if not os.path.exists(path):
        return defecto
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defecto


def _escribir_json(path, datos):
    try:
        os.makedirs(os.path.dirname(path) or DATA_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def clave_busqueda(filtros):
    partes = [
        str(filtros.get("nicho", "")).strip().lower(),
        str(filtros.get("plataforma", "")).strip().lower(),
        str(filtros.get("pais", "")).strip().lower(),
        str(filtros.get("seguidores", "")).strip().lower(),
        str(filtros.get("idioma_creador", "")).strip().lower(),
    ]
    return hashlib.md5("|".join(partes).encode()).hexdigest()[:12]


def clave_legible(filtros):
    return (f"{filtros.get('nicho', '?')} · {filtros.get('plataforma', '?')} · "
            f"{filtros.get('pais', '?')} · {filtros.get('seguidores', '?')}")


def buscar_en_cache(filtros, ttl_horas=TTL_HORAS_DEFECTO):
    cache = _leer_json(CACHE_PATH, {})
    resultados = _leer_json(RESULT_PATH, {})
    clave = clave_busqueda(filtros)
    entrada = cache.get(clave)
    if not entrada:
        return None
    try:
        guardado = dt.datetime.fromisoformat(entrada["fecha"])
    except (KeyError, ValueError):
        return None
    edad_horas = (dt.datetime.now() - guardado).total_seconds() / 3600
    if edad_horas > ttl_horas:
        return None
    return resultados.get(entrada["id"])


def guardar_resultado(filtros, resultados, marca="—", fuente="desconocida",
                      ttl_horas=TTL_HORAS_DEFECTO):
    clave = clave_busqueda(filtros)
    id_resultado = f"t_{dt.datetime.now():%Y%m%d}_{uuid.uuid4().hex[:6]}"
    ahora = dt.datetime.now().isoformat(timespec="seconds")
    normalizados = []
    for r in resultados:
        item = dict(r)
        item.setdefault("estado_contacto", "pendiente")
        item.setdefault("notas", "")
        normalizados.append(item)
    registro = {
        "id": id_resultado, "clave": clave, "clave_legible": clave_legible(filtros),
        "fecha": ahora, "ttl_horas": ttl_horas, "filtros": filtros, "marca": marca,
        "fuente": fuente, "resultados": normalizados,
    }
    resultados_db = _leer_json(RESULT_PATH, {})
    resultados_db[id_resultado] = registro
    _escribir_json(RESULT_PATH, resultados_db)
    cache = _leer_json(CACHE_PATH, {})
    cache[clave] = {"id": id_resultado, "fecha": ahora}
    _escribir_json(CACHE_PATH, cache)
    historial = _leer_json(HIST_PATH, [])
    historial.append({"id": id_resultado, "clave": clave, "fecha": ahora, "marca": marca,
                      "fuente": fuente, "n_resultados": len(normalizados)})
    _escribir_json(HIST_PATH, historial)
    return registro


def listar_busquedas():
    resultados = _leer_json(RESULT_PATH, {})
    return sorted(resultados.values(), key=lambda r: r.get("fecha", ""), reverse=True)


def actualizar_contacto(id_resultado, indice, estado=None, notas=None):
    resultados_db = _leer_json(RESULT_PATH, {})
    reg = resultados_db.get(id_resultado)
    if not reg or indice >= len(reg["resultados"]):
        return False
    item = reg["resultados"][indice]
    if estado is not None:
        item["estado_contacto"] = estado
    if notas is not None:
        item["notas"] = notas
    _escribir_json(RESULT_PATH, resultados_db)
    return True


def borrar_busqueda(id_resultado):
    resultados_db = _leer_json(RESULT_PATH, {})
    reg = resultados_db.pop(id_resultado, None)
    if not reg:
        return False
    _escribir_json(RESULT_PATH, resultados_db)
    cache = _leer_json(CACHE_PATH, {})
    cache.pop(reg.get("clave"), None)
    _escribir_json(CACHE_PATH, cache)
    return True


def limpiar_caducadas(ttl_horas=TTL_HORAS_DEFECTO):
    ahora = dt.datetime.now()
    resultados_db = _leer_json(RESULT_PATH, {})
    borrados = []
    for id_r, reg in list(resultados_db.items()):
        try:
            edad = (ahora - dt.datetime.fromisoformat(reg["fecha"])).total_seconds() / 3600
        except (KeyError, ValueError):
            edad = 9999
        if edad > ttl_horas:
            borrados.append(id_r)
            resultados_db.pop(id_r, None)
    if borrados:
        _escribir_json(RESULT_PATH, resultados_db)
        cache = _leer_json(CACHE_PATH, {})
        for k, v in list(cache.items()):
            if v.get("id") in borrados:
                cache.pop(k, None)
        _escribir_json(CACHE_PATH, cache)
    return len(borrados)


def resumen_metricas():
    busquedas = listar_busquedas()
    total_creadores = sum(len(b.get("resultados", [])) for b in busquedas)
    pendientes = sum(1 for b in busquedas for it in b.get("resultados", [])
                     if it.get("estado_contacto", "pendiente") == "pendiente")
    return {"prospecciones": len(busquedas), "creadores": total_creadores,
            "pendientes": pendientes}


# --- Programación automática ---
def guardar_pieza(post_id, imagen_bytes):
    try:
        os.makedirs(PIEZAS_DIR, exist_ok=True)
        ruta = os.path.join(PIEZAS_DIR, f"{post_id}.jpg")
        with open(ruta, "wb") as f:
            f.write(imagen_bytes)
        return ruta
    except OSError:
        return None


def crear_campana_programada(camp, horas_por_red, dias_semana):
    plan = _leer_json(PLAN_AUTO_PATH, {"campanas": []})
    ahora = dt.datetime.now()
    posts = []
    for red in camp["redes"]:
        hora_txt = horas_por_red.get(red, "10:00")
        try:
            hh, mm = map(int, hora_txt.split(":"))
        except ValueError:
            hh, mm = 10, 0
        publicacion = camp["publicaciones"].get(red, {})
        texto = texto_final(publicacion,
                            enlace_utm(camp["brief"]["url"], red, camp["nombre"]), red)
        imagen = camp["piezas"].get(red)
        for dia in range(dias_semana):
            fecha = (ahora + dt.timedelta(days=dia)).replace(
                hour=hh, minute=mm, second=0, microsecond=0)
            if fecha < ahora:
                continue
            post_id = f"p_{fecha:%Y%m%d%H%M}_{uuid.uuid4().hex[:4]}"
            pieza_path = guardar_pieza(post_id, imagen) if imagen else None
            posts.append({
                "id": post_id,
                "marca": camp["marca"],
                "red": red,
                "fecha_programada": fecha.isoformat(timespec="minutes"),
                "texto": texto,
                "titulo": publicacion.get("titulo", ""),
                "hashtags": publicacion.get("hashtags", []),
                "gancho": camp.get("gancho", ""),
                "pieza_path": pieza_path,
                "estado": "pendiente",
                "intentos": 0,
                "ultimo_error": "",
                "enlace_publicado": "",
            })
    campana_prog = {
        "id": f"camp_{ahora:%Y%m%d%H%M%S}",
        "nombre": camp["nombre"],
        "marca": camp["marca"],
        "estado": "aprobada",
        "fecha_creacion": ahora.isoformat(timespec="seconds"),
        "posts": posts,
    }
    plan["campanas"] = plan.get("campanas", []) + [campana_prog]
    _escribir_json(PLAN_AUTO_PATH, plan)
    return campana_prog


# =====================================================================
# 6) BUSCADOR DE TALENTOS
# =====================================================================
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

RANGOS = {
    "Cualquiera": (0, 10**12),
    "Nano (1k - 10k)": (1_000, 10_000),
    "Micro (10k - 100k)": (10_000, 100_000),
    "Medio (100k - 500k)": (100_000, 500_000),
    "Grande (+500k)": (500_000, 10**12),
}

PAISES = {
    "España": ("ES", "es"), "México": ("MX", "es"), "Argentina": ("AR", "es"),
    "Colombia": ("CO", "es"), "Estados Unidos": ("US", "en"), "Reino Unido": ("GB", "en"),
    "Global (inglés)": (None, "en"),
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
BUSQUEDAS_SECTOR = {
    "Trading e inversión": ["trading bolsa", "análisis técnico acciones"],
    "Criptomonedas": ["criptomonedas bitcoin", "trading cripto"],
    "Finanzas personales": ["finanzas personales", "educación financiera"],
    "DJs y música electrónica": ["DJ set techno", "DJ música electrónica"],
    "Producción musical": ["producción musical", "home studio beats"],
    "Creadores de contenido y audio": ["edición de audio podcast", "creador de contenido"],
    "Tecnología e IA": ["inteligencia artificial herramientas", "tecnología software"],
    "Emprendimiento y marketing": ["marketing digital", "emprendimiento negocios online"],
}
AFINIDAD_MINIMA = 5

ACTIVIDAD = {"Cualquiera": None, "Último mes": 30, "Últimos 3 meses": 90, "Últimos 6 meses": 180}
CACHE_HORAS = 6
_cache_busquedas = {}

PERFILES = ["Creadores de contenido / influencers", "Educadores y formadores",
            "Comunidades y grupos", "Medios, blogs y newsletters", "Podcasts",
            "Profesionales del sector", "Empresas o marcas complementarias"]

SITIOS_API = {"YouTube (datos oficiales)": "youtube", "Bluesky (datos oficiales)": "bluesky"}
SITIOS_IA = ["Instagram", "TikTok", "X (Twitter)", "LinkedIn", "Twitch",
             "Facebook (páginas y grupos)", "Telegram (canales)", "Discord (servidores)",
             "Reddit (comunidades)", "Podcasts (Spotify / Apple)",
             "Newsletters (Substack y similares)", "Webs y blogs", "Threads"]

ESTADOS_CRM = ["🔍 Encontrado", "✉️ Contactado", "💬 Respondió", "🤝 Colaborando", "❌ Descartado"]
COLUMNAS = ["afinidad", "nombre", "red", "tipo", "ultima_publicacion", "seguidores",
            "interaccion", "verificado", "media_vistas", "contacto", "url", "motivo",
            "descripcion"]

SECTOR_POR_MARCA = {"AdeskCharts": "Trading e inversión",
                    "SoundSnip Studio PRO": "DJs y música electrónica",
                    "PublishFlow": "Tecnología e IA"}


def _cacheado(clave, funcion):
    guardado = _cache_busquedas.get(clave)
    if guardado and time.time() - guardado[0] < CACHE_HORAS * 3600:
        return [dict(r) for r in guardado[1]], True
    resultado = funcion()
    _cache_busquedas[clave] = (time.time(), [dict(r) for r in resultado])
    return resultado, False


def _fecha(texto):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(texto or ""))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def dias_sin_publicar(texto):
    f = _fecha(texto)
    return (dt.date.today() - f).days if f else None


def _llamar_gemini(client, modelos, contents, config=None):
    if hasattr(client, "generar"):
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


def buscar_youtube(consulta, pais, max_res=25, key=None, dias=None):
    if not key:
        key = SECRETOS.get("YOUTUBE_API_KEY", "")
    if not key:
        raise RuntimeError("falta YOUTUBE_API_KEY en los Secrets.")
    region, idioma = PAISES[pais]
    params = {"part": "snippet", "q": consulta, "maxResults": max_res,
              "relevanceLanguage": idioma, "key": key}
    if region:
        params["regionCode"] = region
    ultima = {}
    if dias:
        desde = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)
        params.update(type="video", publishedAfter=desde.strftime("%Y-%m-%dT%H:%M:%SZ"))
    else:
        params["type"] = "channel"
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=10)
    r.raise_for_status()
    ids = []
    for it in r.json().get("items", []):
        sn = it.get("snippet", {})
        cid = it.get("id", {}).get("channelId") or sn.get("channelId")
        if not cid:
            continue
        if cid not in ids:
            ids.append(cid)
        if dias:
            ultima[cid] = max(ultima.get(cid, ""), sn.get("publishedAt", ""))
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
            "nombre": sn.get("title", ""), "red": "YouTube",
            "url": f"https://www.youtube.com/{handle}" if handle
                   else f"https://www.youtube.com/channel/{c['id']}",
            "seguidores": subs, "media_vistas": vistas // videos if videos else 0,
            "contacto": _emails(desc), "descripcion": desc[:300],
            "ultima_publicacion": ultima.get(c["id"], "")[:10],
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

    def ultima_bsky(handle):
        try:
            f = requests.get(base + "app.bsky.feed.getAuthorFeed",
                             params={"actor": handle, "limit": 1, "filter": "posts_no_replies"},
                             timeout=10).json().get("feed", [])
            return f[0]["post"].get("indexedAt", "")[:10] if f else ""
        except Exception:
            return ""

    perfiles = r2.json().get("profiles", [])
    with ThreadPoolExecutor(max_workers=8) as ex:
        fechas = list(ex.map(ultima_bsky, [p["handle"] for p in perfiles]))
    resultados = []
    for p, fecha in zip(perfiles, fechas):
        desc = p.get("description", "") or ""
        resultados.append({
            "nombre": p.get("displayName") or p["handle"], "red": "Bluesky",
            "url": f"https://bsky.app/profile/{p['handle']}",
            "seguidores": int(p.get("followersCount", 0) or 0),
            "media_vistas": None, "contacto": _emails(desc), "descripcion": desc[:300],
            "ultima_publicacion": fecha,
        })
    return resultados


PALABRAS_RUIDO = {
    "bolso", "bolsos", "cartera", "carteras", "marroquinería", "moda", "complementos",
    "empleo", "trabajo", "oferta de empleo", "currículum", "cv",
    "plástico", "plásticos", "embalaje", "packaging",
    "supermercado", "compra", "descuentos", "cupones",
    "regalo", "regalos", "manualidades", "bebé", "niños", "cocina", "recetas",
    "mascotas", "perros", "gatos", "viajes", "turismo", "hoteles",
    "ropa", "zapatos", "joyas", "bisutería", "perfumes",
}


def _encaja_con_sector(perfil, sector):
    texto = " ".join([
        str(perfil.get("nombre", "")),
        str(perfil.get("descripcion", "")),
        str(perfil.get("tipo", "")),
    ]).lower()
    if any(p in texto for p in PALABRAS_RUIDO):
        return False
    palabras_sector = [p.strip().lower()
                       for p in SECTORES.get(sector, sector).split(",") if p.strip()]
    return any(p in texto for p in palabras_sector)


def _filtrar_por_sector(candidatos, sector, diag=None):
    antes = len(candidatos)
    filtrados = [c for c in candidatos if _encaja_con_sector(c, sector)]
    descartados = antes - len(filtrados)
    if descartados and diag is not None:
        diag.append(f"Filtro de sector ({sector}): {descartados} perfiles descartados.")
    return filtrados


def _url_viva(url, timeout=4):
    if not url or not url.startswith("http"):
        return False
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 PublishFlow"})
        if r.status_code == 405:
            r = requests.get(url, timeout=timeout, allow_redirects=True, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 PublishFlow"})
            r.close()
        return r.status_code < 400
    except Exception:
        return False


def _comprobar_urls(candidatos, diag=None):
    if not candidatos:
        return candidatos
    with ThreadPoolExecutor(max_workers=10) as ex:
        ok = list(ex.map(lambda c: _url_viva(c.get("url", "")), candidatos))
    vivos = [c for c, k in zip(candidatos, ok) if k]
    rotos = len(candidatos) - len(vivos)
    if rotos and diag is not None:
        diag.append(f"Comprobación de enlaces: {rotos} perfiles descartados por URL rota.")
    return vivos


def buscar_con_ia(client, modelos, marca_desc, sector, extra, perfiles, redes, rango, pais,
                  n=30, diag=None, dias=None):
    actividad_txt = (f"solo perfiles con publicaciones en los últimos {dias} días" if dias
                     else "da igual, pero mejor si siguen activos")
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
- Prioriza perfiles activos con vía de contacto profesional pública.
- Enlaza siempre al perfil.
- Si no conoces un dato, deja el campo vacío o a 0.
- Si no encuentras {n} perfiles REALES del sector exacto, devuelve MENOS. Es mejor 5 buenos.
- NUNCA incluyas perfiles solo porque su nombre contenga la palabra clave.
- ACTIVIDAD: {actividad_txt}.

Responde ÚNICAMENTE con un array JSON:
[{{"nombre": "", "red": "", "tipo": "", "url": "", "seguidores": 0, "contacto": "",
  "ultima_publicacion": "", "descripcion": ""}}]
"""
    config = None
    if _GENAI_DISPONIBLE and types is not None:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())])
    try:
        texto = _llamar_gemini(client, modelos, prompt, config)
    except Exception as e:
        if type(e).__name__ != "SinBusquedaWeb" or not hasattr(client, "generar"):
            raise
        if diag is not None:
            diag.append("Ninguna IA puede buscar en internet ahora mismo. Datos puede ser antiguos.")
        prompt_sin_web = f"""
Eres un especialista en marketing de influencers. Propón hasta {n} perfiles públicos conocidos
del sector indicado. Solo perfiles que estés razonablemente seguro de que existen.

SECTOR: {sector}
TEMAS: {SECTORES.get(sector, sector)}
REDES: {", ".join(redes)}
PAÍS / IDIOMA: {pais}

Devuelve: {{"perfiles": [{{"nombre": "", "red": "", "tipo": "", "url": "", "seguidores": 0,
  "contacto": "", "descripcion": ""}}]}}
"""
        texto = client.generar(prompt_sin_web, buscar_web=False, json_mode=True)
    datos = _extraer_json(texto)
    if datos is None and diag is not None:
        diag.append("El agente IA respondió, pero no en el formato esperado.")
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
            "nombre": str(d.get("nombre", "")), "red": f"{d.get('red', 'Web')} (IA)",
            "tipo": str(d.get("tipo", "")), "url": url, "seguidores": seguidores,
            "media_vistas": None, "contacto": str(d.get("contacto", "")),
            "descripcion": str(d.get("descripcion", ""))[:300],
            "ultima_publicacion": str(_fecha(d.get("ultima_publicacion")) or ""),
        })
    return resultados


def usuario_instagram(url):
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", url or "")
    if not m or m.group(1).lower() in ("p", "reel", "explore", "stories", "accounts"):
        return ""
    return m.group(1)


def verificar_instagram(usuario, cred):
    version = cred.get("FB_GRAPH_VERSION") or "v23.0"
    campos = (f"business_discovery.username({usuario})"
              "{username,name,biography,website,followers_count,media_count,"
              "media.limit(6){like_count,comments_count,timestamp}}")
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
    fechas = sorted((p.get("timestamp", "")[:10] for p in medias if p.get("timestamp")),
                    reverse=True)
    return {"seguidores": seguidores, "interaccion": interaccion,
            "ultima_publicacion": fechas[0] if fechas else "",
            "contacto": contacto, "bio": bio[:300], "nombre": bd.get("name") or usuario}


def instagram_conectado(cred):
    return bool(cred and cred.get("IG_USER_ID") and cred.get("FB_PAGE_TOKEN"))


def seleccionar_mejores(client, modelos, marca_desc, sector, rango, candidatos, top=20):
    if not candidatos:
        return candidatos
    resumen = [{"i": i, "nombre": c["nombre"], "red": c["red"], "tipo": c.get("tipo", ""),
                "seguidores": c["seguidores"], "interaccion": c.get("interaccion"),
                "verificado": c.get("verificado", ""), "tiene_contacto": bool(c["contacto"]),
                "dias_sin_publicar": dias_sin_publicar(c.get("ultima_publicacion")),
                "descripcion": c["descripcion"][:150]}
               for i, c in enumerate(candidatos)]
    prompt = f"""
Eres responsable de alianzas. Puntúa de 1 a 10 cada perfil como posible embajador, afiliado
o colaborador.

SECTOR BUSCADO: {sector}
TAMAÑO PREFERIDO: {rango}
MARCA: {marca_desc}

Criterios por orden: encaje temático, perfil real y activo, contacto público,
frecuencia de publicación, tamaño.

PERFILES: {json.dumps(resumen, ensure_ascii=False)}

Responde SOLO con: [{{"i": 0, "afinidad": 7, "motivo": "frase"}}]
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
    puntuados = any("afinidad" in c for c in candidatos)
    if puntuados:
        candidatos = [c for c in candidatos if c.get("afinidad", 0) >= AFINIDAD_MINIMA]
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
- Termina con una pregunta sencilla.
"""
    return _llamar_gemini(client, modelos, prompt)


# =====================================================================
# 7) CSS
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;800&family=Manrope:wght@400;600;700;800&display=swap');
:root { --violeta: #A855F7; --lila: #C084FC; --fucsia: #F472B6; --cian: #22D3EE;
        --ambar: #FBBF24; --verde: #34D399; --azul: #60A5FA;
        --tinta: #0A0514; --panel: #170D2C; --texto: #EDE7FF; --suave: #B7A8D9; }
html, body, .stMarkdown, .stButton button, label, p { font-family: 'Manrope', system-ui, sans-serif; }
h1, h2, h3 { font-family: 'Sora', 'Manrope', sans-serif !important; letter-spacing: -0.01em; }
.stApp { background:
    radial-gradient(900px 480px at -5% -10%, rgba(168,85,247,.26), transparent 60%),
    radial-gradient(700px 420px at 105% -5%, rgba(244,114,182,.16), transparent 60%),
    radial-gradient(800px 500px at 50% 115%, rgba(34,211,238,.10), transparent 60%),
    var(--tinta); }
h1 { background: linear-gradient(90deg, var(--cian), var(--lila) 45%, var(--fucsia));
     -webkit-background-clip: text; background-clip: text; color: transparent !important;
     filter: drop-shadow(0 0 16px rgba(192,132,252,.5)); font-size: 2.6rem !important; }
h2, h3 { color: #F5EFFF !important; text-shadow: 0 0 18px rgba(192,132,252,.35); }
hr { border: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--lila), var(--cian), transparent); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #170B2E, var(--tinta));
                            border-right: 1px solid rgba(168,85,247,.35);
                            box-shadow: 4px 0 24px rgba(168,85,247,.12); }
.stTabs [role="tablist"] { gap: 8px; border-bottom: 1px solid rgba(168,85,247,.25);
                           padding-bottom: 0; overflow-x: auto; }
.stTabs [role="tab"] { --c: var(--lila); min-height: 56px; padding: 0 22px; display: flex;
  align-items: center; border-radius: 14px 14px 0 0; background: rgba(23,13,44,.75);
  border: 1px solid rgba(168,85,247,.2); border-bottom: none; transition: box-shadow .2s ease; }
.stTabs [role="tab"] p { font-size: 1.1rem !important; font-weight: 800; color: var(--suave); }
.stTabs [role="tab"]:nth-child(1) { --c: var(--lila); }
.stTabs [role="tab"]:nth-child(2) { --c: var(--cian); }
.stTabs [role="tab"]:nth-child(3) { --c: var(--fucsia); }
.stTabs [role="tab"]:nth-child(4) { --c: var(--ambar); }
.stTabs [role="tab"]:nth-child(5) { --c: var(--verde); }
.stTabs [role="tab"]:nth-child(6) { --c: var(--azul); }
.stTabs [role="tab"]:nth-child(7) { --c: #E879F9; }
.stTabs [role="tab"]:nth-child(8) { --c: #F97316; }
.stTabs [role="tab"]:nth-child(9) { --c: #22C55E; }
.stTabs [role="tab"]:hover p { color: var(--c); }
.stTabs [role="tab"][aria-selected="true"], .stTabs [role="tab"][data-selected="true"] {
  background: color-mix(in srgb, var(--c) 18%, #170D2C); border-color: var(--c);
  box-shadow: 0 -2px 20px color-mix(in srgb, var(--c) 50%, transparent); }
.stTabs [role="tab"][aria-selected="true"] p, .stTabs [role="tab"][data-selected="true"] p {
  color: var(--c) !important; text-shadow: 0 0 12px var(--c); }
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"] {
  background: var(--c, var(--lila)) !important; height: 3px; box-shadow: 0 0 12px var(--c, var(--lila)); }
.stTabs [data-baseweb="tab-border"] { display: none; }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button,
.stDownloadButton > button {
  background: linear-gradient(90deg, #7C3AED, #C026D3 60%, #DB2777); color: #fff; border: 0;
  font-weight: 700; box-shadow: 0 0 16px rgba(192,38,211,.45); transition: box-shadow .2s ease; }
.stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover,
.stDownloadButton > button:hover { box-shadow: 0 0 26px rgba(244,114,182,.8); color: #fff; }
.stButton > button[kind="secondary"] { border: 1px solid rgba(34,211,238,.5); color: var(--cian); }
.stButton > button[kind="secondary"]:hover { box-shadow: 0 0 14px rgba(34,211,238,.5); color: var(--cian); }
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--cian) !important; box-shadow: 0 0 0 1px var(--cian), 0 0 14px rgba(34,211,238,.4); }
[data-testid="stExpander"] { border: 1px solid rgba(168,85,247,.35); border-radius: 14px;
                             background: rgba(23,13,44,.6); }
[data-testid="stExpander"] summary p { font-weight: 800; font-size: 1.02rem; }
[data-testid="stAlert"] { border-left: 3px solid var(--cian); border-radius: 12px;
                          box-shadow: 0 0 16px rgba(34,211,238,.12); }
[data-testid="stDataFrame"], [data-testid="stCode"] { border: 1px solid rgba(168,85,247,.3);
                                                     border-radius: 12px; }
.miembro { --acento: var(--lila); border: 1px solid color-mix(in srgb, var(--acento) 55%, transparent);
  border-top: 3px solid var(--acento); border-radius: 20px; padding: 24px 16px 20px;
  text-align: center; background: linear-gradient(180deg,
  color-mix(in srgb, var(--acento) 12%, #170D2C), rgba(23,13,44,.9) 55%);
  margin-bottom: 18px; box-shadow: 0 0 28px color-mix(in srgb, var(--acento) 22%, transparent); }
.miembro img { width: 150px; height: 150px; border-radius: 50%; object-fit: cover;
  object-position: center 30%; background: var(--panel); border: 4px solid var(--tinta);
  box-shadow: 0 0 0 3px var(--acento), 0 0 30px color-mix(in srgb, var(--acento) 80%, transparent); }
.miembro .nombre { font-family: 'Sora', sans-serif; font-weight: 800; font-size: 1.15rem;
                   margin-top: 14px; color: #FFFFFF; }
.miembro .rol { color: var(--acento); font-size: .95rem; font-weight: 700;
                text-shadow: 0 0 10px color-mix(in srgb, var(--acento) 60%, transparent); }
.miembro .bio { color: var(--suave); font-size: .86rem; margin-top: 8px; line-height: 1.45; }
.miembro .estado { display: inline-block; margin-top: 12px; padding: 4px 12px; border-radius: 999px;
  font-size: .8rem; font-weight: 700; color: var(--acento);
  border: 1px solid color-mix(in srgb, var(--acento) 60%, transparent);
  background: color-mix(in srgb, var(--acento) 10%, transparent); }
.miembro .estado.libre { color: #8E80B3; border-color: rgba(142,128,179,.35); background: none; }
.firma { --acento: var(--lila); display: flex; align-items: center; gap: 14px; margin: 6px 0 16px; }
.firma img { width: 68px; height: 68px; border-radius: 50%; object-fit: cover;
  object-position: center 30%; border: 3px solid var(--tinta);
  box-shadow: 0 0 0 2px var(--acento), 0 0 18px color-mix(in srgb, var(--acento) 75%, transparent); }
.firma b { color: #FFFFFF; font-size: 1.05rem; }
.firma span { color: var(--acento); font-size: .92rem; font-weight: 700; }
.marca-badge { display: inline-block; padding: 4px 14px; border-radius: 999px;
  background: linear-gradient(90deg, rgba(34,211,238,.18), rgba(192,132,252,.18));
  border: 1px solid rgba(192,132,252,.5); color: #F5EFFF; font-weight: 700;
  font-size: .95rem; letter-spacing: .02em; margin-bottom: 8px; }
@media (max-width: 640px) {
  .stTabs [role="tab"] { min-height: 48px; padding: 0 14px; }
  .stTabs [role="tab"] p { font-size: .95rem !important; }
  .miembro img { width: 120px; height: 120px; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 8) EQUIPO: fotos y tarjetas
# =====================================================================
def foto_fija(id_miembro, nombre):
    base = os.path.dirname(os.path.abspath(__file__))
    for carpeta in ("fotos", "assets", ""):
        for ext in ("jpg", "jpeg", "png", "webp"):
            ruta = os.path.join(base, carpeta, f"{id_miembro}.{ext}")
            if os.path.exists(ruta):
                mime = "jpeg" if ext in ("jpg", "jpeg") else ext
                with open(ruta, "rb") as f:
                    return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    semilla = nombre.replace(" ", "%20")
    return f"https://api.dicebear.com/9.x/notionists/png?seed={semilla}&backgroundColor=2a1650"


def foto_src(id_miembro, nombre):
    propia = st.session_state.fotos_equipo.get(id_miembro)
    if propia:
        return "data:image/jpeg;base64," + base64.b64encode(propia).decode()
    return foto_fija(id_miembro, nombre)


COLORES_EQUIPO = {"estrategia": "#C084FC", "copy": "#22D3EE", "creativa": "#F472B6",
                  "community": "#FBBF24", "analista": "#34D399", "talento": "#60A5FA"}


def color_de(m):
    return m.get("color") or COLORES_EQUIPO.get(m["id"], "#C084FC")


def firma(id_miembro):
    m = EQ[id_miembro]
    st.markdown(
        f'<div class="firma" style="--acento:{color_de(m)}">'
        f'<img src="{foto_src(m["id"], m["nombre"])}">'
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
    return (f'<div class="miembro" style="--acento:{color_de(m)}">'
            f'<img src="{foto_src(m["id"], m["nombre"])}">'
            f'<div class="nombre">{m["nombre"]}</div><div class="rol">{m["rol"]}</div>'
            f'<div class="bio">{m["bio"]}</div><div class="{clase}">● {estado}</div></div>')


# =====================================================================
# 9) ESTADO DE SESIÓN
# =====================================================================
st.session_state.setdefault("campana", None)
st.session_state.setdefault("registro", [])
st.session_state.setdefault("fotos_equipo", {})
st.session_state.setdefault("colaboradores", [])
st.session_state.setdefault("resultados_talento", [])
st.session_state.setdefault("diagnostico_talento", [])
st.session_state.setdefault("cred_marcas", {m: {} for m in MARCAS})
if "marcas_custom" not in st.session_state:
    st.session_state["marcas_custom"] = _cargar_marcas_custom()
if "marca_activa" not in st.session_state:
    st.session_state["marca_activa"] = list(MARCAS)[0]

if SECRETOS.get("APP_PASSWORD") and not st.session_state.get("autenticado"):
    st.title("PublishFlow")
    clave = st.text_input("Contraseña", type="password")
    if st.button("Entrar", type="primary"):
        if clave == str(SECRETOS["APP_PASSWORD"]):
            st.session_state.autenticado = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    st.stop()


# =====================================================================
# 10) HELPERS
# =====================================================================
def icono_red(red, cred):
    if REDES[red]["tipo"] == "manual":
        return "⬇️"
    return "🟢" if conectado(red, cred) else "⚪"


def ejecutar_campana(brief, fotos, logo, color, redes, idioma, tono):
    client = get_gemini_client()
    with st.status("El equipo está trabajando en tu campaña…", expanded=True) as estado:
        st.write(f"🧭 {EQ['estrategia']['nombre']} está analizando mercados, público y horarios…")
        estrategia = crear_estrategia(client, MODELOS_VALIDOS, brief, redes, idioma, fotos)
        st.write(f"✍️ {EQ['copy']['nombre']} está escribiendo las publicaciones…")
        copy = escribir_publicaciones(client, MODELOS_VALIDOS, brief, estrategia,
                                      redes, idioma, tono)
        st.write(f"🎨 {EQ['creativa']['nombre']} está preparando las piezas visuales y el guion…")
        gancho = copy.get("gancho_imagen", "")
        piezas = {}
        for i, red in enumerate(redes):
            foto = fotos[i % len(fotos)] if fotos else None
            piezas[red] = crear_pieza(foto, REDES[red]["tamano"], color, gancho, logo)
        guion = escribir_guion(client, MODELOS_VALIDOS, brief, estrategia, idioma, tono)
        st.write(f"📅 {EQ['community']['nombre']} está organizando la publicación…")
        publicaciones = copy.get("publicaciones", {})
        for red in redes:
            publicaciones.setdefault(red, {"texto": "", "variante_b": "", "hashtags": []})
        estado.update(label="Campaña lista. Revisa las entregas del equipo.",
                      state="complete", expanded=False)
    ahora = dt.datetime.now()
    return {
        "id": ahora.strftime("%Y%m%d%H%M%S"),
        "fecha": ahora.strftime("%d/%m/%Y %H:%M"),
        "brief": brief, "marca": brief["marca"],
        "nombre": f"{brief['marca']} {ahora.strftime('%d-%m')}",
        "redes": redes, "estrategia": estrategia, "gancho": gancho,
        "publicaciones": publicaciones, "piezas": piezas, "guion": guion,
    }


def textos_campana(camp):
    return {red: texto_final(camp["publicaciones"][red],
                             enlace_utm(camp["brief"]["url"], red, camp["nombre"]), red)
            for red in camp["redes"]}


def horarios(camp):
    return {r.get("red"): ", ".join(r.get("horarios", []))
            for r in camp["estrategia"].get("redes", []) if isinstance(r, dict)}


def tabla(datos):
    if isinstance(datos, list) and datos:
        st.dataframe(pd.DataFrame(datos), hide_index=True)


# =====================================================================
# 11) BARRA LATERAL
# =====================================================================
with st.sidebar:
    st.markdown("### 🎯 Marca activa")
    todas_marcas = marcas_todas()
    marca_activa = st.radio(
        "Marca activa", list(todas_marcas),
        key="marca_activa", label_visibility="collapsed",
    )
    CRED = cred_marca(marca_activa)

    with st.expander("➕ Añadir / gestionar marcas"):
        st.markdown("**Añadir marca personalizada**")
        with st.form("nueva_marca_form", clear_on_submit=True):
            nuevo_nombre = st.text_input("Nombre de la marca",
                                         placeholder="Ej.: VoltAuto")
            nueva_desc = st.text_area(
                "¿Qué es? (una frase)", height=80,
                placeholder="Ej.: Coches eléctricos urbanos con 500 km de autonomía")
            nueva_url = st.text_input("Web", placeholder="https://voltauto.com")
            nuevo_color = st.color_picker("Color de marca", value="#00A8E8")
            crear = st.form_submit_button("Crear marca", type="primary")
        if crear:
            nombre_limpio = (nuevo_nombre or "").strip()
            if not nombre_limpio:
                st.error("Pon un nombre a la marca.")
            elif nombre_limpio in todas_marcas:
                st.error(f"Ya existe una marca llamada «{nombre_limpio}».")
            else:
                st.session_state.marcas_custom[nombre_limpio] = {
                    "descripcion": (nueva_desc or "").strip(),
                    "url": (nueva_url or "").strip(),
                    "color": nuevo_color,
                    "prefijo": prefijo_desde_nombre(nombre_limpio),
                }
                _guardar_marcas_custom()
                st.session_state.marca_activa = nombre_limpio
                st.success(f"Marca «{nombre_limpio}» creada. Seleccionada como activa.")
                st.rerun()

        if st.session_state.marcas_custom:
            st.markdown("**Marcas personalizadas**")
            for nombre in list(st.session_state.marcas_custom):
                c1, c2 = st.columns([4, 1])
                with c1:
                    pref = st.session_state.marcas_custom[nombre].get("prefijo", "?")
                    st.caption(f"🎨 **{nombre}** · prefijo `{pref}_`")
                with c2:
                    if st.button("🗑️", key=f"del_marca_{nombre}",
                                 help=f"Borrar «{nombre}»"):
                        st.session_state.marcas_custom.pop(nombre, None)
                        _guardar_marcas_custom()
                        if st.session_state.marca_activa == nombre:
                            st.session_state.marca_activa = list(MARCAS)[0]
                        st.rerun()

    st.divider()
    st.subheader("Ajustes de la agencia")
    idioma = st.selectbox("Idioma de las publicaciones",
                          ["Español", "Inglés", "Portugués", "Francés", "Alemán"])
    tono = st.selectbox("Tono de voz",
                        ["Cercano / Amigable", "Profesional", "Persuasivo", "Educativo",
                         "Humorístico", "Urgente / Directo"])

    st.divider()
    st.subheader("Inteligencia artificial")
    for nombre_ia, icono_ia, detalle_ia in GestorIA.desde_secretos(SECRETOS).estado():
        st.caption(f"{icono_ia} **{nombre_ia}**: {detalle_ia}")
    with st.expander("Probar cada IA"):
        if st.button("Probar todas las IA", key="btn_probar_ia"):
            with st.spinner("Probando las claves…"):
                for nombre_ia, ok_ia, detalle_ia in GestorIA.desde_secretos(SECRETOS).diagnosticar():
                    (st.success if ok_ia else st.error)(f"{nombre_ia}: {detalle_ia}")

    st.divider()
    conectadas = [r for r in CONECTORES if conectado(r, CRED)]
    st.markdown(f"**Redes conectadas: {len(conectadas)} / {len(CONECTORES)}**")
    for r in conectadas:
        st.caption(f"🟢 {r}")

    st.divider()
    st.subheader("📊 Resumen rápido")
    _m = resumen_metricas()
    st.caption(f"Prospecciones: **{_m['prospecciones']}**")
    st.caption(f"Creadores en base: **{_m['creadores']}**")
    st.caption(f"Pendientes de contacto: **{_m['pendientes']}**")

    # Resumen de automatización
    _plan = _leer_json(PLAN_AUTO_PATH, {"campanas": []})
    _pendientes_auto = sum(1 for c in _plan.get("campanas", [])
                            for p in c.get("posts", []) if p.get("estado") == "pendiente")
    st.caption(f"Posts programados: **{_pendientes_auto}**")

    st.divider()
    with st.expander("⚙️ Avanzado"):
        st.caption("Claves que la app encuentra en tus Secrets (valores ocultos):")
        st.code("\n".join(sorted(SECRETOS)) or "(ninguno)", language=None)
        if st.session_state.get("error_secrets"):
            st.error("Error leyendo Secrets: " + st.session_state["error_secrets"])


# =====================================================================
# 12) PESTAÑAS
# =====================================================================
(tab_oficina, tab_encargo, tab_entregas, tab_programacion, tab_publicar,
 tab_resultados, tab_seguimiento, tab_talento, tab_conexiones) = st.tabs(
    ["🏢 Oficina", "📋 Nuevo encargo", "📦 Entregas", "📅 Programación", "📤 Publicación",
     "📈 Resultados", "📊 Seguimiento", "🤝 Talento", "🔌 Conexiones"]
)


with tab_oficina:
    st.markdown(f'<div class="marca-badge">🎯 Trabajando para: {marca_activa}</div>',
                unsafe_allow_html=True)
    st.title("Tu agencia de marketing")
    st.write("Seis especialistas para tus marcas. Encarga una campaña y cada uno te entrega su parte.")
    columnas = st.columns(3)
    for i, m in enumerate(EQUIPO):
        with columnas[i % 3]:
            st.markdown(tarjeta(m), unsafe_allow_html=True)
    camp = st.session_state.campana
    if camp:
        st.subheader(f"Campaña en curso: {camp['marca']}")
        st.write(camp["estrategia"].get("resumen", ""))
        st.caption(f"Encargada el {camp['fecha']}. Revisa el trabajo en la pestaña Entregas.")
    else:
        st.info("No hay ninguna campaña en marcha. Ve a «Nuevo encargo».")


with tab_encargo:
    st.markdown(f'<div class="marca-badge">🎯 Trabajando para: {marca_activa}</div>',
                unsafe_allow_html=True)
    st.subheader("Briefing para el equipo")
    marca = marca_activa
    datos_marca = marcas_todas()[marca]
    c1, c2 = st.columns(2)
    with c1:
        descripcion = st.text_area("Qué quieres promocionar",
                                   value=datos_marca["descripcion"], height=120,
                                   key=f"desc_{marca}")
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
        color = st.color_picker("Color de marca", value=datos_marca["color"],
                                key=f"color_{marca}")
    redes = st.multiselect(
        "Redes de la campaña", list(REDES),
        default=[r for r in REDES if conectado(r, CRED)] + ["X (Twitter)"],
        format_func=lambda r: f"{icono_red(r, CRED)} {r}",
    )
    st.caption("🟢 conectada  ⚪ se puede conectar en 🔌 Conexiones  ⬇️ descarga para subir a mano")
    if st.button("Encargar campaña al equipo", type="primary"):
        if not descripcion.strip():
            st.warning("Describe qué quieres promocionar.")
        elif not redes:
            st.warning("Elige al menos una red.")
        else:
            brief = {"marca": marca, "descripcion": descripcion, "url": url.strip(),
                     "objetivo": objetivo, "mercado": mercado, "publico": publico,
                     "oferta": oferta}
            fotos = [f.getvalue() for f in (fotos_subidas or [])]
            logo = logo_subido.getvalue() if logo_subido else None
            try:
                st.session_state.campana = ejecutar_campana(brief, fotos, logo, color,
                                                            redes, idioma, tono)
                st.success("Campaña lista. Tienes el trabajo del equipo en «Entregas».")
            except Exception as e:
                st.error(f"El equipo no pudo terminar la campaña: {e}")


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
                pub["titulo"] = st.text_input("Título", pub.get("titulo", ""),
                                              key=f"tit_{camp['id']}_{red}")
                pub["texto"] = st.text_area(red, pub.get("texto", ""),
                                            height=260 if REDES[red].get("articulo") else 150,
                                            key=f"txt_{camp['id']}_{red}",
                                            label_visibility="collapsed")
                tags = st.text_input("Hashtags", " ".join(pub.get("hashtags", [])),
                                     key=f"tag_{camp['id']}_{red}")
                pub["hashtags"] = tags.split()
                final = texto_final(pub, enlace_utm(camp["brief"]["url"], red, camp["nombre"]), red)
                st.caption(f"{len(final)} de {REDES[red]['limite']} caracteres")
                if pub.get("variante_b"):
                    st.caption(f"Variante B: {pub['variante_b']}")
        with st.expander("Piezas visuales y guion de vídeo", expanded=True):
            firma("creativa")
            cols = st.columns(3)
            for i, red in enumerate(camp["redes"]):
                w, h = REDES[red]["tamano"]
                with cols[i % 3]:
                    st.image(camp["piezas"][red], caption=f"{red} ({w}×{h})")
            st.markdown("---")
            st.markdown(camp["guion"])

        st.divider()
        st.markdown("### ✅ ¿Todo listo?")
        st.caption("Si estás conforme con los textos y las imágenes, ve a la pestaña "
                   "**📅 Programación** para elegir horarios y activar el envío automático.")


with tab_programacion:
    st.markdown(f'<div class="marca-badge">🎯 Programando para: {marca_activa}</div>',
                unsafe_allow_html=True)
    st.subheader("📅 Programación automática")
    st.caption("Aprueba una campaña y GitHub Actions la publicará sola cada día a las horas "
               "indicadas, sin que tú tengas que hacer nada.")

    camp_actual = st.session_state.campana
    if camp_actual:
        st.markdown(f"### Campaña lista para programar: **{camp_actual['nombre']}**")
        st.write(f"Marca: **{camp_actual['marca']}** · "
                 f"Redes: {', '.join(camp_actual['redes'])}")

        st.markdown("#### 🕐 Horarios por red")
        st.caption("Elena (la estratega) recomienda estos horarios según cada red. "
                   "Puedes cambiarlos si prefieres otro momento.")

        rec_default = {
            "LinkedIn": "08:00", "Telegram": "10:00", "Bluesky": "12:30",
            "Discord": "18:00", "Instagram": "19:00", "Facebook": "13:00",
            "Threads": "19:30", "Mastodon": "17:00", "Pinterest": "20:00",
            "WordPress": "09:00", "Blogger (Google)": "09:00",
            "Dev.to": "11:00", "Newsletter (Brevo)": "07:00",
            "X (Twitter)": "20:30", "TikTok": "20:00",
        }
        cols = st.columns(min(3, len(camp_actual["redes"]) or 1))
        horas_por_red = {}
        for i, red in enumerate(camp_actual["redes"]):
            with cols[i % len(cols)]:
                horas_por_red[red] = st.text_input(
                    red, value=rec_default.get(red, "10:00"),
                    key=f"hora_{camp_actual['id']}_{red}",
                    help="Formato HH:MM (24 h)")

        dias = st.slider("¿Cuántos días programar?", 1, 7, 5,
                         help="Se publicará el mismo contenido cada día a esas horas "
                              "durante los días indicados.")

        # Preview de la parrilla
        with st.expander("📋 Ver previsualización de la parrilla", expanded=False):
            for red in camp_actual["redes"]:
                hora = horas_por_red.get(red, "10:00")
                pub = camp_actual["publicaciones"].get(red, {})
                st.markdown(f"**{red}** · todos los días a las {hora}")
                st.caption(f"Título: {pub.get('titulo', '(sin título)')}")
                st.code(pub.get("texto", "")[:200], language=None, wrap_lines=True)

        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            if st.button("✅ Aprobar y programar esta campaña", type="primary"):
                try:
                    prog = crear_campana_programada(camp_actual, horas_por_red, dias)
                    st.success(f"✅ Campaña programada: **{len(prog['posts'])} posts** "
                               f"en {len(camp_actual['redes'])} redes durante {dias} días. "
                               f"Se publicarán solos gracias al cron de GitHub Actions.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo programar: {e}")
        with c2:
            st.caption(f"≈ {dias * len(camp_actual['redes'])} publicaciones en total")
    else:
        st.info("Primero genera una campaña en «📋 Nuevo encargo». "
                "Cuando esté lista, podrás aprobarla aquí.")

    st.divider()

    # Listado de campañas programadas
    st.subheader("📌 Campañas programadas")
    plan = _leer_json(PLAN_AUTO_PATH, {"campanas": []})
    campanas_prog = plan.get("campanas", [])
    if not campanas_prog:
        st.caption("Todavía no hay ninguna campaña programada.")
    else:
        for cp in reversed(campanas_prog):
            posts = cp.get("posts", [])
            pubs = sum(1 for p in posts if p.get("estado") == "publicado")
            pend = sum(1 for p in posts if p.get("estado") == "pendiente")
            err = sum(1 for p in posts if p.get("estado") in ("error", "error_definitivo"))
            with st.expander(f"📌 {cp['nombre']} · {pubs}✅ {pend}⏳ {err}❌"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total", len(posts))
                c2.metric("Publicados", pubs)
                c3.metric("Pendientes", pend)
                c4.metric("Errores", err)
                st.caption(f"Estado: {cp['estado']} · Marca: {cp['marca']} · "
                           f"Creada: {cp.get('fecha_creacion', '')[:16].replace('T', ' ')}")

                # Filtro de estado
                filtro_estado = st.selectbox(
                    "Mostrar", ["Todos", "Pendientes", "Publicados", "Errores"],
                    key=f"filtro_{cp['id']}")
                for p in posts:
                    estado_post = p.get("estado", "pendiente")
                    if filtro_estado == "Pendientes" and estado_post != "pendiente":
                        continue
                    if filtro_estado == "Publicados" and estado_post != "publicado":
                        continue
                    if filtro_estado == "Errores" and estado_post not in ("error", "error_definitivo"):
                        continue
                    fecha_txt = p.get("fecha_programada", "")[:16].replace("T", " ")
                    estado_icono = {"publicado": "✅", "pendiente": "⏳",
                                    "error": "⚠️", "error_definitivo": "❌"}.get(
                        estado_post, "❓")
                    col_info, col_btn = st.columns([5, 1])
                    with col_info:
                        st.caption(f"{estado_icono} {fecha_txt} · {p['red']} · "
                                   f"{p.get('titulo', '')[:40]}")
                        if p.get("estado") == "error_definitivo":
                            st.caption(f"   ↳ {p.get('ultimo_error', '')[:120]}")
                        if p.get("enlace_publicado"):
                            st.markdown(f"   ↳ [Ver publicación]({p['enlace_publicado']})")
                    with col_btn:
                        if estado_post == "pendiente":
                            if st.button("🗑️", key=f"quitar_{p['id']}",
                                         help="Quitar de la cola"):
                                for c in plan["campanas"]:
                                    if c["id"] == cp["id"]:
                                        c["posts"] = [x for x in c["posts"]
                                                       if x["id"] != p["id"]]
                                _escribir_json(PLAN_AUTO_PATH, plan)
                                st.rerun()


with tab_publicar:
    camp = st.session_state.campana
    firma("community")
    if not camp:
        st.info("Cuando el equipo termine una campaña, aquí podrás publicarla manualmente.")
    else:
        textos = textos_campana(camp)
        horas = horarios(camp)
        st.download_button(
            "Descargar todo (ZIP)",
            pack_zip(camp["redes"], camp["piezas"], textos, camp["guion"], camp["estrategia"]),
            file_name=f"{slug(camp['nombre'])}.zip", mime="application/zip",
        )
        st.caption("Publica a la hora que recomienda Elena.")
        for red in camp["redes"]:
            tipo = REDES[red]["tipo"]
            st.divider()
            c1, c2, c3 = st.columns([1, 2.2, 1])
            with c1:
                st.image(camp["piezas"][red], width=170)
            with c2:
                st.markdown(f"**{red}**")
                st.caption(f"{icono_red(red, CRED)} {TIPOS[tipo]}")
                if horas.get(red):
                    st.caption(f"Mejor horario: {horas[red]}")
                st.code(textos[red], language=None, wrap_lines=True)
            with c3:
                clave = f"{camp['id']}_{red}"
                pub = camp["publicaciones"][red]
                if tipo == "auto" and conectado(red, CRED):
                    if st.button(f"Publicar en {red}", key=f"pub_{clave}", type="primary"):
                        try:
                            enlace = publicar(red, textos[red], pub.get("titulo", ""),
                                              camp["piezas"][red], CRED,
                                              pub.get("hashtags", []))
                            st.session_state.registro.append(
                                {"campaña": camp["id"],
                                 "fecha": dt.datetime.now().strftime("%d/%m %H:%M"),
                                 "red": red, "estado": "Publicado", "enlace": enlace})
                            st.success("Publicado.")
                        except Exception as e:
                            st.error(f"No se pudo publicar en {red}: {e}")
                else:
                    if tipo == "auto":
                        st.caption("Sin conectar: hazlo en la pestaña 🔌 Conexiones.")
                    else:
                        st.caption(REDES[red].get("motivo", ""))
                    st.download_button("Descargar imagen", camp["piezas"][red],
                                       file_name=f"{slug(red)}.jpg", mime="image/jpeg",
                                       key=f"img_{clave}")
                    titulo = pub.get("titulo", "")
                    st.download_button("Descargar texto",
                                       (f"{titulo}\n\n" if titulo else "").encode("utf-8")
                                       + textos[red].encode("utf-8"),
                                       file_name=f"{slug(red)}.txt", mime="text/plain",
                                       key=f"txtd_{clave}")
                    if st.button("Marcar como publicada", key=f"man_{clave}"):
                        st.session_state.registro.append(
                            {"campaña": camp["id"],
                             "fecha": dt.datetime.now().strftime("%d/%m %H:%M"),
                             "red": red, "estado": "Publicado a mano", "enlace": ""})
                        st.success("Anotado.")


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
        st.dataframe(pd.DataFrame([{"red": r,
                                    "enlace": enlace_utm(camp["brief"]["url"], r, camp["nombre"])}
                                   for r in camp["redes"]]), hide_index=True)
        st.markdown("**Métricas de la campaña**")
        base = pd.DataFrame([{"red": r, "alcance": 0, "clics": 0, "visitas_web": 0,
                              "suscriptores": 0} for r in camp["redes"]])
        metricas = st.data_editor(base, hide_index=True, disabled=["red"],
                                  key=f"met_{camp['id']}")
        if st.button("Pedir informe a Sara"):
            with st.spinner("Sara está preparando el informe…"):
                try:
                    st.markdown(informe_resultados(get_gemini_client(), MODELOS_VALIDOS,
                                                   camp["brief"], metricas.to_dict("records"),
                                                   idioma))
                except Exception as e:
                    st.error(f"No se pudo generar el informe: {e}")


with tab_seguimiento:
    st.subheader("📊 Seguimiento de publicaciones automáticas")
    st.caption("Todo lo que el cron de GitHub ha publicado por ti, sin que hayas hecho nada.")

    registro = _leer_json(REGISTRO_AUTO_PATH, [])
    if not registro:
        st.info("Aún no hay publicaciones automáticas. Programa una campaña y espera a que "
                "GitHub Actions ejecute el cron (cada 15 min entre las 7 y las 22 h).")
    else:
        total = len(registro)
        pubs = sum(1 for r in registro if r.get("estado") == "publicado")
        errs = total - pubs
        c1, c2, c3 = st.columns(3)
        c1.metric("Publicaciones totales", pubs)
        c2.metric("Errores", errs)
        c3.metric("Tasa de éxito",
                  f"{100*pubs//total}%" if total else "—")

        marcas_disp = sorted({r.get("marca", "") for r in registro})
        marca_filtro = st.multiselect("Filtrar por marca", marcas_disp, default=marcas_disp,
                                       key="seg_marca")
        solo_errores = st.checkbox("Solo errores", key="seg_solo_errores")

        vista = [r for r in registro
                 if r.get("marca") in marca_filtro
                 and (not solo_errores or r.get("estado") != "publicado")]

        if vista:
            df = pd.DataFrame([{
                "fecha": r.get("fecha", "")[:16].replace("T", " "),
                "marca": r.get("marca", ""),
                "red": r.get("red", ""),
                "estado": "✅" if r.get("estado") == "publicado" else "❌",
                "enlace": r.get("enlace", "") or r.get("error", "")[:80],
            } for r in reversed(vista)])
            st.dataframe(df, hide_index=True,
                         column_config={"enlace": st.column_config.LinkColumn("Enlace")})

        errores_activos = [r for r in registro
                           if r.get("estado") != "publicado"
                           and r.get("marca") in marca_filtro]
        if errores_activos:
            st.warning(f"⚠️ {len(errores_activos)} publicaciones fallaron. "
                       "Revisa la pestaña 📅 Programación para ver detalles y reintentar.")


# =====================================================================
# 13) TALENTO
# =====================================================================
def _render_talento_buscar():
    st.subheader("🤝 Buscador de colaboradores, embajadores y afiliados")
    st.caption("Usa solo contactos profesionales públicos, escribe uno a uno con mensajes "
               "personalizados y respeta a quien no quiera colaborar (RGPD).")
    c1, c2 = st.columns(2)
    with c1:
        _mb = marcas_buscador()
        marca_sel = st.selectbox("Marca para la que buscas", list(_mb),
                                 index=list(_mb).index(marca_activa)
                                 if marca_activa in _mb else 0,
                                 key="col_marca")
        marca_desc = _mb.get(marca_sel, "")
        if not marca_desc:
            marca_desc = st.text_input("¿Qué es tu marca? (una frase)", key="col_desc_otra")
        sectores = list(SECTORES)
        sector = st.selectbox("Sector de los colaboradores", sectores,
                              index=sectores.index(SECTOR_POR_MARCA.get(marca_sel, sectores[0])),
                              key=f"col_sector_{marca_sel}")
        extra = st.text_input("Palabras clave extra (opcional)",
                              placeholder="Ej.: análisis técnico, day trading, techno",
                              key="col_extra")
        perfiles = st.multiselect("Tipo de perfil", PERFILES,
                                  default=["Creadores de contenido / influencers",
                                           "Educadores y formadores"],
                                  key="col_perfiles")
    with c2:
        redes_sel = st.multiselect(
            "Dónde buscar", list(SITIOS_API) + SITIOS_IA,
            default=["Instagram", "YouTube (datos oficiales)", "TikTok", "X (Twitter)"],
            key="col_redes",
        )
        rango = st.selectbox("Tamaño de audiencia", list(RANGOS), index=2, key="col_rango")
        pais = st.selectbox("País / idioma", list(PAISES), key="col_pais")
        actividad = st.selectbox("Última publicación", list(ACTIVIDAD), index=2,
                                 key="col_actividad")
        sin_fecha_fuera = st.checkbox("Descartar también si no se conoce la fecha",
                                      key="col_sinfecha")
        top = st.slider("Quedarme con los mejores", 5, 30, 20, key="col_top")
        solo_contacto = st.checkbox("Solo perfiles con contacto público visible", key="col_solo")
        if instagram_conectado(CRED):
            st.caption("✅ Instagram conectado: verificaré seguidores, interacción y contacto reales.")
        else:
            st.caption("ℹ️ Conecta Instagram en 🔌 Conexiones para verificar con datos reales.")
    oferta = st.selectbox("Tipo de colaboración que ofreces", OFERTAS, key="col_oferta")
    col_a, col_b = st.columns(2)
    with col_a:
        usar_base_datos = st.checkbox(
            "⚡ Usar base de datos si existe (ahorra llamadas a la IA)",
            value=True, key="col_usar_bd",
            help="Si ya has buscado este nicho+plataforma+país en los últimos 7 días, "
                 "carga los resultados guardados sin gastar tokens.")
    with col_b:
        forzar_ia = st.checkbox(
            "🔄 Forzar nueva búsqueda (ignora caché)",
            value=False, key="col_forzar",
            help="Marca esta casilla para buscar de nuevo aunque ya exista en la base.")
    if st.button("🔎 Buscar candidatos", type="primary", key="btn_col_buscar"):
        if not redes_sel:
            st.warning("Elige al menos un sitio donde buscar.")
            return
        filtros_busqueda = {
            "nicho": sector + (f" · {extra.strip()}" if extra.strip() else ""),
            "plataforma": " + ".join(redes_sel),
            "pais": pais,
            "seguidores": rango,
            "idioma_creador": PAISES[pais][1],
            "max_resultados": top,
            "marca": marca_sel,
        }
        if usar_base_datos and not forzar_ia:
            cacheado = buscar_en_cache(filtros_busqueda, ttl_horas=TTL_HORAS_DEFECTO)
            if cacheado:
                st.success(
                    f"⚡ Recuperado de la base de datos "
                    f"(guardado el {cacheado['fecha'][:16].replace('T', ' ')}). "
                    f"Sin gastar tokens."
                )
                st.session_state.resultados_talento = cacheado["resultados"]
                st.session_state.diagnostico_talento = [
                    f"Base de datos: {len(cacheado['resultados'])} perfiles recuperados "
                    f"(id `{cacheado['id']}`).",
                    "No se ha llamado a la IA. Marca «🔄 Forzar nueva búsqueda» para actualizar.",
                ]
                return
        client = get_gemini_client()
        res, diag = [], []
        dias = ACTIVIDAD[actividad]
        terminos = ([f"{BUSQUEDAS_SECTOR[sector][0].split()[0]} {extra}".strip()]
                    if extra.strip() else BUSQUEDAS_SECTOR[sector])
        with st.spinner("Buscando perfiles del sector..."):
            if "YouTube (datos oficiales)" in redes_sel:
                try:
                    encontrados, cache = [], False
                    for t in terminos:
                        parte, cache = _cacheado(
                            ("yt", t, pais, dias),
                            lambda t=t: buscar_youtube(
                                t, pais, max_res=15, dias=dias,
                                key=SECRETOS.get("YOUTUBE_API_KEY")))
                        encontrados += parte
                    diag.append(f"YouTube: {len(encontrados)} canales"
                                + (" (caché)." if cache else "."))
                    res += encontrados
                except Exception as e:
                    st.error(f"YouTube: {e}")
            if "Bluesky (datos oficiales)" in redes_sel:
                try:
                    encontrados = []
                    for t in terminos:
                        parte, _ = _cacheado(("bsky", t),
                                             lambda t=t: buscar_bluesky(t, max_res=15))
                        encontrados += parte
                    diag.append(f"Bluesky: {len(encontrados)} perfiles.")
                    res += encontrados
                except Exception as e:
                    st.error(f"Bluesky: {e}")
            redes_ia = [r for r in redes_sel if r in SITIOS_IA]
            if redes_ia:
                try:
                    encontrados, cache = _cacheado(
                        ("ia", sector, extra, tuple(perfiles), tuple(redes_ia), rango, pais, dias),
                        lambda: buscar_con_ia(client, MODELOS_VALIDOS, marca_desc, sector,
                                              extra, perfiles, redes_ia, rango, pais,
                                              n=min(40, max(25, top + 10)), diag=diag,
                                              dias=dias))
                    diag.append(f"Agente IA ({', '.join(redes_ia)}): "
                                f"{len(encontrados)} perfiles"
                                + (" (caché)." if cache else "."))
                    res += encontrados
                except Exception as e:
                    st.error(f"Agente IA: {e}")
        unicos, vistos = [], set()
        for r in res:
            clave = r["url"].lower().rstrip("/")
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(r)
        res = unicos
        res = _filtrar_por_sector(res, sector, diag)
        for r in res:
            r.setdefault("verificado", "")
            r.setdefault("interaccion", None)
        if instagram_conectado(CRED):
            cuentas_ig = [r for r in res if usuario_instagram(r["url"])]
            if cuentas_ig:
                verificadas = 0
                with st.spinner(f"Revisando {len(cuentas_ig)} perfiles de Instagram..."):
                    for r in cuentas_ig:
                        try:
                            datos = verificar_instagram(usuario_instagram(r["url"]), CRED)
                            r.update(seguidores=datos["seguidores"],
                                     interaccion=datos["interaccion"],
                                     contacto=r["contacto"] or datos["contacto"],
                                     descripcion=datos["bio"] or r["descripcion"],
                                     ultima_publicacion=datos["ultima_publicacion"]
                                     or r.get("ultima_publicacion", ""),
                                     verificado="✅ real")
                            verificadas += 1
                        except Exception:
                            r["verificado"] = "⚠️ no verificable"
                diag.append(f"Instagram: {verificadas} de {len(cuentas_ig)} verificados.")
        minimo, maximo = RANGOS[rango]
        antes = len(res)
        def _pasa_tamano(r):
            seg = r.get("seguidores") or 0
            if seg:
                return minimo <= seg <= maximo
            if r["red"] in ("YouTube", "Bluesky") or r.get("verificado") == "✅ real":
                return True
            return False
        res = [r for r in res if _pasa_tamano(r)]
        if antes - len(res):
            diag.append(f"Filtro de tamaño ({rango}): {antes - len(res)} descartados.")
        with st.spinner(f"Comprobando {len(res)} enlaces..."):
            res = _comprobar_urls(res, diag)
        if dias:
            antes = len(res)
            res = [r for r in res
                   if (dias_sin_publicar(r.get("ultima_publicacion")) is None
                       and not sin_fecha_fuera)
                   or (dias_sin_publicar(r.get("ultima_publicacion")) is not None
                       and dias_sin_publicar(r.get("ultima_publicacion")) <= dias)]
            if antes - len(res):
                diag.append(f"Filtro de actividad: {antes - len(res)} descartados.")
        if solo_contacto:
            antes = len(res)
            res = [r for r in res if r["contacto"]]
            if antes - len(res):
                diag.append(f"Filtro «solo con contacto»: {antes - len(res)} descartados.")
        total = len(res)
        if res:
            with st.spinner(f"La IA está eligiendo los {top} mejores de {total}..."):
                res = seleccionar_mejores(client, MODELOS_VALIDOS, marca_desc, sector, rango,
                                          res, top)
            diag.append(f"Selección final: {len(res)} perfiles de {total}.")
        if res:
            registro = guardar_resultado(filtros_busqueda, res, marca=marca_sel,
                                         fuente="buscador")
            diag.append(f"💾 Guardado con id `{registro['id']}`. "
                        "Próxima búsqueda con los mismos filtros no gastará tokens.")
        st.session_state.diagnostico_talento = diag
        st.session_state.resultados_talento = res
    res = st.session_state.resultados_talento
    diag = st.session_state.get("diagnostico_talento")
    if diag:
        with st.expander(f"Cómo ha ido la búsqueda ({len(res)} candidatos)", expanded=not res):
            for linea in diag:
                st.write("• " + linea)
            if not res:
                st.warning("No ha quedado ningún candidato. Prueba a ampliar filtros.")
    if res:
        st.markdown(f"**{len(res)} candidatos encontrados**")
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
                "ultima_publicacion": st.column_config.TextColumn("Última publicación"),
                "verificado": st.column_config.TextColumn("Datos"),
            },
            disabled=[c for c in df.columns if c != "guardar"],
            hide_index=True, key="tabla_resultados",
        )
        if st.button("💾 Guardar seleccionados en mi lista", key="btn_col_guardar"):
            existentes = {c["url"] for c in st.session_state.colaboradores}
            nuevos = 0
            for _, fila in editado[editado["guardar"]].iterrows():
                if fila["url"] in existentes:
                    continue
                d = {k: fila[k] for k in COLUMNAS}
                d.update(marca=marca_sel, estado=ESTADOS_CRM[0], notas="")
                st.session_state.colaboradores.append(d)
                nuevos += 1
            st.success(f"{nuevos} añadidos a tu lista.")
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
            "estado": st.column_config.SelectboxColumn("Estado", options=ESTADOS_CRM),
            "url": st.column_config.LinkColumn("Enlace"),
        },
        disabled=["marca", "nombre", "red", "seguidores", "url"],
        hide_index=True, key="tabla_crm",
    )
    for i, fila in crm_editado.iterrows():
        lista[i].update(estado=fila["estado"], contacto=fila["contacto"], notas=fila["notas"])
    st.download_button("⬇️ Descargar lista (CSV)",
                       pd.DataFrame(lista).to_csv(index=False).encode("utf-8-sig"),
                       "colaboradores.csv", "text/csv", key="btn_col_csv")
    st.markdown("#### ✍️ Mensaje de contacto personalizado")
    nombres = [f"{c['nombre']} ({c['red']})" for c in lista]
    sel = st.selectbox("Para:", range(len(nombres)), format_func=lambda i: nombres[i],
                       key="col_sel")
    idioma_msg = st.selectbox("Idioma del mensaje", ["Español", "Inglés"], key="col_idioma")
    if st.button("✍️ Redactar mensaje", key="btn_col_msg"):
        c = lista[sel]
        desc = marcas_buscador().get(c["marca"]) or marca_desc
        with st.spinner("Redactando..."):
            try:
                st.session_state.col_mensaje = generar_mensaje(
                    get_gemini_client(), MODELOS_VALIDOS, c["marca"], desc, oferta, c, idioma_msg)
            except Exception as e:
                st.error(f"Error al generar el mensaje: {e}")
    if st.session_state.get("col_mensaje"):
        st.text_area("Revísalo y envíalo tú:", st.session_state.col_mensaje, height=230,
                     key=f"col_msg_{hash(st.session_state.col_mensaje)}")


def _render_talento_base():
    st.subheader("Prospecciones guardadas")
    busquedas = listar_busquedas()
    if not busquedas:
        st.info("Aún no hay búsquedas guardadas. Lanza una desde «Buscar».")
        return
    marcas_disponibles = sorted({b.get("marca", "—") for b in busquedas})
    marca_sel = st.multiselect("Filtrar por marca", marcas_disponibles,
                               default=marcas_disponibles, key="tal_filtro_marca")
    m = resumen_metricas()
    c1, c2, c3 = st.columns(3)
    c1.metric("Prospecciones", m["prospecciones"])
    c2.metric("Creadores en base", m["creadores"])
    c3.metric("Pendientes de contacto", m["pendientes"])
    for b in busquedas:
        if b.get("marca") not in marca_sel:
            continue
        etiqueta = (f"📌 {b.get('clave_legible', '—')} · "
                    f"{len(b.get('resultados', []))} perfiles · "
                    f"{b.get('fecha', '')[:16].replace('T', ' ')}")
        with st.expander(etiqueta):
            st.caption(f"id: {b['id']} · fuente: {b.get('fuente', '?')}")
            for i, item in enumerate(b["resultados"]):
                with st.container(border=True):
                    cc1, cc2 = st.columns([3, 1])
                    with cc1:
                        st.markdown(f"### {item.get('nombre', '—')}")
                        st.caption(f"{item.get('red', '—')} · "
                                   f"{item.get('seguidores', '—')} · "
                                   f"afinidad **{item.get('afinidad', '—')}%**")
                        if item.get("descripcion"):
                            st.write(item["descripcion"])
                        if item.get("url"):
                            st.markdown(f"🔗 [Abrir]({item['url']})")
                    with cc2:
                        actual = item.get("estado_contacto", "pendiente")
                        nuevo = st.selectbox(
                            "Estado", ESTADOS_CONTACTO,
                            index=(ESTADOS_CONTACTO.index(actual)
                                   if actual in ESTADOS_CONTACTO else 0),
                            key=f"est_{b['id']}_{i}")
                        notas = st.text_area("Notas", item.get("notas", ""),
                                             key=f"not_{b['id']}_{i}", height=80)
                        if (nuevo != actual) or (notas != item.get("notas", "")):
                            if st.button("💾 Guardar", key=f"sv_{b['id']}_{i}"):
                                actualizar_contacto(b["id"], i, nuevo, notas)
                                st.success("Actualizado.")
                                st.rerun()
            col1, _ = st.columns([1, 5])
            with col1:
                if st.button("🗑️ Borrar", key=f"del_{b['id']}"):
                    borrar_busqueda(b["id"])
                    st.rerun()
    st.divider()
    if st.button("🧹 Limpiar búsquedas caducadas (>7 días)"):
        n = limpiar_caducadas()
        st.success(f"Se borraron {n} prospecciones caducadas.")
        st.rerun()


with tab_talento:
    firma("talento")
    sub_buscar, sub_base = st.tabs(["🔎 Buscar", "🗂️ Base de talentos"])
    with sub_buscar:
        _render_talento_buscar()
    with sub_base:
        _render_talento_base()


# =====================================================================
# 14) CONEXIONES
# =====================================================================
with tab_conexiones:
    st.markdown(f'<div class="marca-badge">🎯 Conectando para: {marca_activa}</div>',
                unsafe_allow_html=True)
    st.subheader("Panel de conexiones")
    st.write(f"Estás configurando las conexiones de **{marca_activa}**. "
             "Cambia de marca en la barra lateral para configurar otras.")

    if st.session_state.get("aviso_conexion"):
        st.success(st.session_state.pop("aviso_conexion"))

    red_sel = st.selectbox("Red", list(REDES),
                           format_func=lambda r: f"{icono_red(r, CRED)} {r}",
                           key="red_conexion")

    if REDES[red_sel]["tipo"] == "manual":
        st.info(f"{red_sel} se publica a mano. {REDES[red_sel].get('motivo', '')} "
                "Daniel te deja la imagen y el texto listos en la pestaña Publicación.")
    else:
        spec = CONECTORES[red_sel]
        ok = conectado(red_sel, CRED)
        st.markdown(f"**Estado:** {'🟢 Conectado' if ok else '⚪ Sin conectar'}")
        for dep in spec.get("requiere", []):
            st.caption(f"Necesita {dep} conectado ({icono_red(dep, CRED)}).")
        with st.expander("Cómo conseguir estos datos", expanded=not ok):
            st.markdown(spec["pasos"])
        with st.form(f"form_{marca_activa}_{red_sel}"):
            valores = {}
            for c in spec["campos"]:
                actual = CRED.get(c["clave"], "")
                etiqueta = c["etiqueta"] + (" (opcional)" if c["opcional"] else "")
                valores[c["clave"]] = st.text_input(
                    etiqueta, value=str(actual) if actual else "",
                    type="password" if c["secreto"] else "default", help=c["ayuda"])
            enviar = st.form_submit_button("Probar y guardar", type="primary")
        if enviar:
            nuevos = {k: v.strip() for k, v in valores.items() if v.strip()}
            with st.spinner(f"Probando la conexión con {red_sel}…"):
                try:
                    mensaje = probar(red_sel, {**CRED, **nuevos})
                    st.session_state.cred_marcas.setdefault(marca_activa, {}).update(nuevos)
                    st.session_state.aviso_conexion = (
                        f"{red_sel} conectado para {marca_activa}. {mensaje}")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo conectar {red_sel}: {e}")
        claves_marca = st.session_state.cred_marcas.get(marca_activa, {})
        if any(k in claves_marca for k in claves_de(red_sel)):
            if st.button("Desconectar", key=f"descon_{marca_activa}_{red_sel}"):
                for k in claves_de(red_sel):
                    st.session_state.cred_marcas[marca_activa].pop(k, None)
                st.rerun()

    st.divider()
    st.markdown(f"**Estado de todas las redes para {marca_activa}**")
    st.dataframe(pd.DataFrame([
        {"Red": r, "Tipo": TIPOS[REDES[r]["tipo"]],
         "Estado": ("⬇️ Manual" if REDES[r]["tipo"] == "manual"
                    else "🟢 Conectada" if conectado(r, CRED) else "⚪ Sin conectar")}
        for r in REDES]), hide_index=True)

    claves_sesion = st.session_state.cred_marcas.get(marca_activa, {})
    if claves_sesion:
        st.markdown("**Guardar las conexiones para siempre**")
        st.caption(f"Copia este bloque en Streamlit → Settings → Secrets. "
                   f"Las claves llevan el prefijo `{marcas_todas()[marca_activa]['prefijo']}_` "
                   f"para que la app sepa que son de {marca_activa}.")
        st.code(secrets_toml(claves_sesion, marcas_todas()[marca_activa]["prefijo"]),
                language="toml")

    st.divider()
    st.markdown("**⚙️ Configuración de GitHub Actions (para automatizar)**")
    st.caption("Para que las publicaciones se envíen solas cada día, añade las mismas claves "
               "en GitHub → Settings → Secrets and variables → Actions. "
               "Y en tu Streamlit Secrets, añade también la clave del cron.")
        with st.expander("Ver instrucciones completas"):
        st.markdown("""
**1. En GitHub (tu repo) → Settings → Secrets and variables → Actions**

Añade estos secretos, uno por cada clave, con el prefijo de la marca:

- `ADESK_TELEGRAM_BOT_TOKEN`
- `ADESK_TELEGRAM_CHAT_ID`
- `ADESK_BLUESKY_HANDLE`
- `ADESK_BLUESKY_APP_PASSWORD`
- `ADESK_DISCORD_WEBHOOK_URL`
- `SOUNDSNIP_TELEGRAM_BOT_TOKEN`
- `SOUNDSNIP_TELEGRAM_CHAT_ID`
- `PUBLISHFLOW_TELEGRAM_BOT_TOKEN`
- `PUBLISHFLOW_TELEGRAM_CHAT_ID`

**2. El cron se activa solo** con el archivo `.github/workflows/auto_publish.yml`.

**3. Puedes lanzarlo a mano** en GitHub → Actions → Publicación automática → Run workflow.

**4. Frecuencia del cron:** cada 15 min entre las 7:00 y las 22:59 UTC.
Esto cubre cualquier hora de publicación que configures.
""")
