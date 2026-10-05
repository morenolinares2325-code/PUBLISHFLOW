"""
Gestor de IA de PublishFlow con 3 claves en cascada:

  1. Gemini gratis   (GEMINI_API_KEY)
  2. Groq            (GROQ_API_KEY)
  3. Gemini de pago  (GEMINI_API_KEY_PAGO)  -> opcional, se usa solo si existe

Cada proveedor busca solo sus modelos disponibles y elige el más adecuado.
Si un proveedor agota su cuota (error 429 en todos sus modelos), queda en pausa
unos minutos y la petición pasa automáticamente al siguiente.
"""
import io
import re
import time
import base64

import requests
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError

PAUSA_AGOTADO = 10 * 60          # segundos que un proveedor descansa tras agotar su cuota
CACHE_MODELOS = 60 * 60          # cada cuánto se vuelve a consultar la lista de modelos
MAX_MODELOS_POR_PROVEEDOR = 4    # cuántos modelos prueba cada proveedor antes de pasar al siguiente

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

# Estado compartido mientras la app está encendida
_agotado_hasta = {}
_cache_modelos = {}
_ultimo_uso = {"proveedor": None, "modelo": None}
_ultimo_error = {}


class Agotado(Exception):
    pass


class ClaveInvalida(Exception):
    pass


class SinBusquedaWeb(Exception):
    """El proveedor funciona, pero no tiene ningún modelo capaz de buscar en internet."""
    pass


def _limpiar(valor):
    return str(valor or "").strip().strip('"').strip("'")


def buscar_clave(secretos, tipo):
    for nombre in ALIAS[tipo]:
        valor = _limpiar(secretos.get(nombre))
        if valor:
            return valor
    # Búsqueda flexible: nombres mal escritos o valores reconocibles (AIza... = Google, gsk_... = Groq)
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


# -------------------------------------------------------------------
# Elección automática de modelos
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# Gestor
# -------------------------------------------------------------------
class GestorIA:
    def __init__(self, proveedores):
        self.proveedores = proveedores   # lista de (nombre, tipo, clave)

    @classmethod
    def desde_secretos(cls, secretos):
        proveedores = []
        for nombre, tipo in (("Gemini gratis", "gemini"), ("Groq", "groq"),
                             ("Gemini de pago", "pago")):
            clave = buscar_clave(secretos, tipo)
            if clave:
                proveedores.append((nombre, tipo, clave))
        return cls(proveedores)

    # --- llamadas a cada proveedor ---
    def _gemini(self, clave, preferir_pro, prompt, imagenes, json_mode, buscar_web):
        client = genai.Client(api_key=clave)
        args = {}
        if buscar_web:
            args["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        elif json_mode:
            args["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**args) if args else None
        contents = list(imagenes or []) + [prompt]

        cuota, ultimo = False, None
        for modelo in modelos_gemini(client, clave, preferir_pro)[:MAX_MODELOS_POR_PROVEEDOR + 2]:
            try:
                r = client.models.generate_content(model=modelo, contents=contents, config=config)
                if r and r.text:
                    return r.text, modelo
            except APIError as e:
                ultimo, texto = e, str(e)
                codigo = getattr(e, "code", None)
                if codigo in (401, 403) or "API_KEY_INVALID" in texto:
                    raise ClaveInvalida("La clave de Gemini no es válida.")
                if codigo == 429 or "RESOURCE_EXHAUSTED" in texto:
                    # "limit: 0" = ese modelo no está incluido en el plan gratis: probar otro
                    if "limit: 0" not in texto:
                        cuota = True
                elif codigo in (500, 503):
                    time.sleep(1)
            except Exception as e:
                ultimo = e
        if cuota:
            raise Agotado("Cuota de Gemini agotada.")
        raise RuntimeError(f"Gemini no respondió: {str(ultimo)[:300]}")

    def _groq(self, clave, prompt, imagenes, json_mode, buscar_web):
        cab = {"Authorization": f"Bearer {clave}"}
        cuota, ultimo = False, None
        modelos = modelos_groq(clave, buscar_web, bool(imagenes))
        if buscar_web:
            # Solo los modelos "compound" de Groq pueden buscar en internet
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

    # --- punto de entrada único ---
    def generar(self, prompt, imagenes=None, json_mode=False, buscar_web=False):
        if not self.proveedores:
            raise RuntimeError("No hay ninguna clave de IA configurada en los Secrets.")
        errores, sin_web = [], False
        for nombre, tipo, clave in self.proveedores:
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
                _ultimo_error.pop(nombre, None)
                return texto
            except SinBusquedaWeb as e:
                errores.append(f"{nombre}: {e}")
                sin_web = True
            except Agotado as e:
                _agotado_hasta[nombre] = time.time() + PAUSA_AGOTADO
                _ultimo_error[nombre] = str(e)
                errores.append(f"{nombre}: {e}")
            except Exception as e:
                _ultimo_error[nombre] = str(e)[:300]
                errores.append(f"{nombre}: {e}")
        if buscar_web and sin_web:
            raise SinBusquedaWeb(" | ".join(errores))
        raise RuntimeError("Ninguna IA pudo responder. " + " | ".join(errores))

    def estado(self):
        """Lista de (nombre, icono, detalle) para mostrar en la app."""
        configurados = {n for n, _, _ in self.proveedores}
        filas = []
        for nombre in ("Gemini gratis", "Groq", "Gemini de pago"):
            if nombre not in configurados:
                filas.append((nombre, "⚪", "sin clave"))
            elif _agotado_hasta.get(nombre, 0) > time.time():
                minutos = int((_agotado_hasta[nombre] - time.time()) // 60) + 1
                filas.append((nombre, "🔴", f"cuota agotada, vuelve en {minutos} min"))
            elif _ultimo_error.get(nombre):
                filas.append((nombre, "🟠", f"falló: {_ultimo_error[nombre][:120]}"))
            elif _ultimo_uso["proveedor"] == nombre:
                filas.append((nombre, "🟢", f"en uso: {_ultimo_uso['modelo']}"))
            else:
                filas.append((nombre, "🟢", "lista"))
        return filas

    def diagnosticar(self):
        """Prueba cada clave por separado. Devuelve (nombre, ok, detalle)."""
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
