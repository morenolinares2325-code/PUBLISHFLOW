"""Nombre que importa buscador_colaboradores.py. La implementación está en motor.py."""
from motor import (  # noqa: F401
    ESTADOS_CONTACTO,
    actualizar_contacto,
    borrar_busqueda,
    buscar_en_cache,
    guardar_resultado,
    limpiar_caducadas,
    listar_busquedas,
    obtener_busqueda,
    resumen_metricas,
)
