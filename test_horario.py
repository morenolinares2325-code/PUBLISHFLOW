import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from horario import en_ventana, parse_fecha, proximas_fechas

ZONA = ZoneInfo("Europe/Madrid")


class HorarioTest(unittest.TestCase):
    def test_hora_pasada_no_entra_hoy(self):
        ahora = dt.datetime(2026, 6, 15, 18, 0, tzinfo=ZONA)
        fechas = proximas_fechas(ahora, 10, 0, 5)
        self.assertEqual(len(fechas), 5)
        self.assertEqual(fechas[0], dt.datetime(2026, 6, 16, 10, 0, tzinfo=ZONA))
        self.assertEqual(fechas[-1], dt.datetime(2026, 6, 20, 10, 0, tzinfo=ZONA))

    def test_hora_futura_de_hoy_si_cuenta(self):
        ahora = dt.datetime(2026, 6, 15, 8, 0, tzinfo=ZONA)
        fechas = proximas_fechas(ahora, 10, 30, 2)
        self.assertEqual(fechas[0], dt.datetime(2026, 6, 15, 10, 30, tzinfo=ZONA))
        self.assertEqual(fechas[1], dt.datetime(2026, 6, 16, 10, 30, tzinfo=ZONA))

    def test_ventana_incluye_el_instante_y_el_margen(self):
        ahora = dt.datetime(2026, 6, 15, 10, 20, tzinfo=ZONA)
        self.assertTrue(en_ventana("2026-06-15T10:00+02:00", ahora))
        self.assertTrue(en_ventana("2026-06-15T10:20+02:00", ahora))
        self.assertFalse(en_ventana("2026-06-15T10:21+02:00", ahora))
        self.assertFalse(en_ventana("2026-06-15T09:50+02:00", ahora))

    def test_fecha_sin_zona_se_lee_como_madrid(self):
        ahora = dt.datetime(2026, 1, 10, 10, 10, tzinfo=ZONA)
        fecha = parse_fecha("2026-01-10T10:00")
        self.assertEqual(fecha.tzinfo, ZONA)
        self.assertTrue(en_ventana("2026-01-10T10:00", ahora))


if __name__ == "__main__":
    unittest.main()
