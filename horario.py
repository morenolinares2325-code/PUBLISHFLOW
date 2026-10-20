"""Horas de publicación en Europe/Madrid, compartidas por la app y publisher.py."""
import datetime as dt
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("Europe/Madrid")
MARGEN = dt.timedelta(minutes=25)


def ahora_madrid():
    return dt.datetime.now(ZONA)


def parse_fecha(texto, zona=ZONA):
    fecha = dt.datetime.fromisoformat(str(texto))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=zona)
    return fecha.astimezone(zona)


def en_ventana(fecha_programada, ahora, margen=MARGEN):
    """True si la hora ya llegó y todavía cabe en el margen del cron."""
    delta = ahora - parse_fecha(fecha_programada)
    return dt.timedelta(0) <= delta <= margen


def proximas_fechas(ahora, hora, minuto, dias):
    """Las próximas `dias` ocurrencias de HH:MM, sin incluir una hora ya pasada hoy."""
    fechas = []
    dia = 0
    while len(fechas) < dias and dia < dias + 3:
        fecha = (ahora + dt.timedelta(days=dia)).replace(
            hour=hora, minute=minuto, second=0, microsecond=0)
        dia += 1
        if fecha <= ahora:
            continue
        fechas.append(fecha)
    return fechas
