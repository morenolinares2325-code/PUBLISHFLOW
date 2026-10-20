import os
import tempfile
import unittest
from unittest.mock import MagicMock

import github_sync


class Respuesta:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text or self.status_code)


class SubirTest(unittest.TestCase):
    def test_un_commit_con_todos_los_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "plan.json")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("{}")
            http = MagicMock()
            http.get.side_effect = [
                Respuesta({"object": {"sha": "padre"}}),
                Respuesta({"tree": {"sha": "arbol-base"}}),
            ]
            http.post.side_effect = [
                Respuesta({"sha": "blob1"}),
                Respuesta({"sha": "arbol-nuevo"}),
                Respuesta({"sha": "abcdef1234567890"}),
            ]
            http.patch.return_value = Respuesta({})
            sha = github_sync.subir([ruta, os.path.join(tmp, "no-existe.jpg")],
                                    "programar", "token", "user/repo", sesion=http)
        self.assertEqual(sha, "abcdef1")
        self.assertEqual(http.post.call_count, 3)
        arbol = http.post.call_args_list[1].kwargs["json"]["tree"]
        self.assertEqual(len(arbol), 1)
        self.assertTrue(arbol[0]["path"].endswith("plan.json"))

    def test_sin_credenciales_no_llama_a_la_red(self):
        resultado = github_sync.sincronizar(["no-existe"], "x", token="", repo="")
        self.assertFalse(resultado["ok"])
        self.assertIn("GITHUB_TOKEN", resultado["detalle"])


if __name__ == "__main__":
    unittest.main()
