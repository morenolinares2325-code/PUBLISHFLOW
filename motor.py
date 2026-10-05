import json
import os
import re
import time
from google import genai
from groq import Groq

# Caché en memoria para no saturar pidiendo la lista de modelos en cada clic
_CACHE_MODELOS = {"gemini": None, "groq": None, "ts": 0}


def obtener_modelos_gemini_vivos(api_key):
    """Consulta en tiempo real a Google qué modelos están activos y operativos."""
    global _CACHE_MODELOS
    ahora = time.time()

    # Refresca la lista cada 30 minutos
    if _CACHE_MODELOS["gemini"] and (ahora - _CACHE_MODELOS["ts"] < 1800):
        return _CACHE_MODELOS["gemini"]

    try:
        client = genai.Client(api_key=api_key)
        disponibles = []
        for m in client.models.list():
            nombre = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            # Solo modelos de texto/multimodal que sirvan para marketing
            if any(x in nombre.lower() for x in ["tts", "embedding", "imagen", "veo", "whisper"]):
                continue

            metodos = getattr(m, "supported_generation_methods", []) or []
            if not metodos or "generateContent" in metodos:
                disponibles.append(nombre)

        # Priorizar: flash-lite y flash primero (menos propensos a colapso de cuota), luego versiones altas
        def criterio(nom):
            nom_l = nom.lower()
            puntos = 0
            if "flash" in nom_l:
                puntos += 60
            if "lite" in nom_l:
                puntos += 20  # Muy estable y rápido en tier gratis
            if "pro" in nom_l:
                puntos += 30  # Mejor redacción pero cuota más estricta
            numeros = re.findall(r"\d+\.?\d*", nom_l)
            if numeros:
                try:
                    puntos += float(numeros[0]) * 10
                except ValueError:
                    pass
            return puntos

        disponibles.sort(key=criterio, reverse=True)
        if disponibles:
            _CACHE_MODELOS["gemini"] = disponibles
            _CACHE_MODELOS["ts"] = ahora
            return disponibles
    except Exception:
        pass

    # Fallback por si la llamada a list() tiene problemas de permisos
    return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def obtener_modelos_groq_vivos(api_key):
    """Consulta a los servidores de Groq qué modelos están activos."""
    try:
        client = Groq(api_key=api_key)
        lista = client.models.list()
        modelos = [m.id for m in lista.data if "whisper" not in m.id.lower()]
        # Priorizar Llama 3.3 70B, luego 3.1 70B / 8B
        modelos.sort(
            key=lambda x: (
                "3.3" in x,
                "70b" in x,
                "3.1" in x,
                "versatile" in x
            ),
            reverse=True
        )
        return modelos if modelos else ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    except Exception:
        return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def _ejecutar_gemini(api_key, prompt, response_schema=None):
    client = genai.Client(api_key=api_key)
    candidatos = obtener_modelos_gemini_vivos(api_key)
    ultimo_error = None

    for modelo in candidatos:
        try:
            config = {}
            if response_schema:
                config["response_mime_type"] = "application/json"
                config["response_schema"] = response_schema

            resp = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=config if config else None
            )
            if resp.text:
                return resp.text, f"Gemini ({modelo})"
        except Exception as e:
            err = str(e).lower()
            ultimo_error = e
            # Si el modelo está retirado o saturado temporalmente, prueba el siguiente de la lista
            if any(k in err for k in ["404", "not found", "503", "unavailable", "overloaded"]):
                continue
            # Si es cuota total diaria agotada (429), lanza excepción para saltar a Groq
            if "429" in err or "quota" in err or "resource_exhausted" in err:
                raise RuntimeError(f"Cuota agotada en esta clave ({modelo}): {e}")
            continue

    raise RuntimeError(f"Ningún modelo de Gemini respondió: {ultimo_error}")


def _ejecutar_groq(api_key, prompt, response_schema=None):
    client = Groq(api_key=api_key)
    candidatos = obtener_modelos_groq_vivos(api_key)
    
    if response_schema:
        prompt_final = f"{prompt}\n\nIMPORTANTE: Responde ÚNICAMENTE en formato JSON válido que cumpla este esquema:\n{json.dumps(response_schema)}"
    else:
        prompt_final = prompt

    ultimo_error = None
    for modelo in candidatos:
        try:
            resp_fmt = {"type": "json_object"} if response_schema else None
            res = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Eres un especialista de marketing y redacción de la agencia PublishFlow."},
                    {"role": "user", "content": prompt_final}
                ],
                model=modelo,
                response_format=resp_fmt
            )
            txt = res.choices[0].message.content
            if txt:
                return txt, f"Groq ({modelo})"
        except Exception as e:
            ultimo_error = e
            err = str(e).lower()
            if "429" in err or "rate limit" in err:
                raise RuntimeError(f"Límite de Groq alcanzado: {e}")
            continue

    raise RuntimeError(f"Ningún modelo de Groq respondió: {ultimo_error}")


def llamar_ia_multinivel(credenciales, prompt, response_schema=None):
    """
    Ruta en cascada inteligente:
    1. Gemini Free (autodetecta modelo vivo)
    2. Groq (autodetecta modelo vivo)
    3. Gemini Pago (autodetecta modelo vivo)
    """
    errores = []

    # 1. NIVEL 1: Gemini Gratuita
    k1 = credenciales.get("GEMINI_FREE_KEY") or os.getenv("GEMINI_FREE_KEY")
    if k1:
        try:
            texto, motor_info = _ejecutar_gemini(k1, prompt, response_schema)
            return texto, f"🟢 Nivel 1 (Gratis) -> {motor_info}"
        except Exception as e:
            errores.append(f"Nivel 1 (Gemini Free) falló: {e}")

    # 2. NIVEL 2: Groq
    k2 = credenciales.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if k2:
        try:
            texto, motor_info = _ejecutar_groq(k2, prompt, response_schema)
            return texto, f"🟡 Nivel 2 (Groq) -> {motor_info}"
        except Exception as e:
            errores.append(f"Nivel 2 (Groq) falló: {e}")

    # 3. NIVEL 3: Gemini Pago
    k3 = credenciales.get("GEMINI_PAID_KEY") or os.getenv("GEMINI_PAID_KEY")
    if k3:
        try:
            texto, motor_info = _ejecutar_gemini(k3, prompt, response_schema)
            return texto, f"🔴 Nivel 3 (Pago) -> {motor_info}"
        except Exception as e:
            errores.append(f"Nivel 3 (Gemini Pago) falló: {e}")

    detalle = "\n".join(f"- {err}" for err in errores)
    raise RuntimeError(f"Todas las opciones fallaron. Detalles:\n{detalle}")
