# almacen_talentos.py
"""
Persistencia de prospecciones del Buscador de Talentos.
Aislado del resto de la app: solo lo usa buscador_colaboradores.py.
Solo librerías estándar de Python.
"""
import json
import os
import hashlib
import datetime as dt
import uuid

DATA_DIR = "data"
CACHE_PATH = os.path.join(DATA_DIR, "talentos_cache.json")
RESULT_PATH = os.path.join(DATA_DIR, "talentos_resultados.json")
HIST_PATH = os.path.join(DATA_DIR, "talentos_historial.json")

TTL_HORAS_DEFECTO = 168  # 7 días

ESTADOS_CONTACTO = ["pendiente", "contactado", "respondido", "cerrado", "descartado"]


# -------------------------------------------------------------------
# Utilidades de disco (atómicas y tolerantes a fallos)
# -------------------------------------------------------------------
def _leer(path, defecto):
    if not os.path.exists(path):
        return defecto
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defecto


def _escribir(path, datos):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# -------------------------------------------------------------------
# Clave de búsqueda (SIN max_resultados, para reutilizar más)
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# Consulta con TTL
# -------------------------------------------------------------------
def buscar_en_cache(filtros, ttl_horas=TTL_HORAS_DEFECTO):
    cache = _leer(CACHE_PATH, {})
    resultados = _leer(RESULT_PATH, {})
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


# -------------------------------------------------------------------
# Guardado
# -------------------------------------------------------------------
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
        "id": id_resultado,
        "clave": clave,
        "clave_legible": clave_legible(filtros),
        "fecha": ahora,
        "ttl_horas": ttl_horas,
        "filtros": filtros,
        "marca": marca,
        "fuente": fuente,
        "resultados": normalizados,
    }

    resultados_db = _leer(RESULT_PATH, {})
    resultados_db[id_resultado] = registro
    _escribir(RESULT_PATH, resultados_db)

    cache = _leer(CACHE_PATH, {})
    cache[clave] = {"id": id_resultado, "fecha": ahora}
    _escribir(CACHE_PATH, cache)

    historial = _leer(HIST_PATH, [])
    historial.append({
        "id": id_resultado, "clave": clave, "fecha": ahora,
        "marca": marca, "fuente": fuente,
        "n_resultados": len(normalizados),
    })
    _escribir(HIST_PATH, historial)

    return registro


# -------------------------------------------------------------------
# Gestión
# -------------------------------------------------------------------
def listar_busquedas():
    resultados = _leer(RESULT_PATH, {})
    return sorted(resultados.values(), key=lambda r: r.get("fecha", ""), reverse=True)


def obtener_busqueda(id_resultado):
    return _leer(RESULT_PATH, {}).get(id_resultado)


def actualizar_contacto(id_resultado, indice, estado=None, notas=None):
    resultados_db = _leer(RESULT_PATH, {})
    reg = resultados_db.get(id_resultado)
    if not reg or indice >= len(reg["resultados"]):
        return False
    item = reg["resultados"][indice]
    if estado is not None:
        item["estado_contacto"] = estado
    if notas is not None:
        item["notas"] = notas
    _escribir(RESULT_PATH, resultados_db)
    return True


def borrar_busqueda(id_resultado):
    resultados_db = _leer(RESULT_PATH, {})
    reg = resultados_db.pop(id_resultado, None)
    if not reg:
        return False
    _escribir(RESULT_PATH, resultados_db)
    cache = _leer(CACHE_PATH, {})
    cache.pop(reg.get("clave"), None)
    _escribir(CACHE_PATH, cache)
    return True


def limpiar_caducadas(ttl_horas=TTL_HORAS_DEFECTO):
    ahora = dt.datetime.now()
    resultados_db = _leer(RESULT_PATH, {})
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
        _escribir(RESULT_PATH, resultados_db)
        cache = _leer(CACHE_PATH, {})
        for k, v in list(cache.items()):
            if v.get("id") in borrados:
                cache.pop(k, None)
        _escribir(CACHE_PATH, cache)
    return len(borrados)


def resumen_metricas():
    busquedas = listar_busquedas()
    total_creadores = sum(len(b.get("resultados", [])) for b in busquedas)
    pendientes = sum(
        1 for b in busquedas for it in b.get("resultados", [])
        if it.get("estado_contacto", "pendiente") == "pendiente"
    )
    return {
        "prospecciones": len(busquedas),
        "creadores": total_creadores,
        "pendientes": pendientes,
    }
