"""Sube el plan y las piezas al repositorio en un solo commit.

GitHub Actions publica leyendo el repo, no el disco efímero de Streamlit.
Sin GITHUB_TOKEN y GITHUB_REPO la función no hace nada y lo dice en el detalle.
"""
import base64
import os

import requests

API = "https://api.github.com"


def _credenciales(secretos=None, token=None, repo=None, branch=None):
    secretos = secretos or {}
    token = token or os.environ.get("GITHUB_TOKEN") or secretos.get("GITHUB_TOKEN") or ""
    repo = repo or os.environ.get("GITHUB_REPO") or secretos.get("GITHUB_REPO") or ""
    branch = branch or os.environ.get("GITHUB_BRANCH") or secretos.get("GITHUB_BRANCH") or "main"
    return str(token).strip(), str(repo).strip(), str(branch).strip() or "main"


def _cabeceras(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def subir(paths, mensaje, token, repo, branch="main", sesion=None):
    """Crea blobs, un árbol y un commit, y mueve la rama. Devuelve el sha corto."""
    http = sesion or requests
    cab = _cabeceras(token)
    ref = http.get(f"{API}/repos/{repo}/git/ref/heads/{branch}", headers=cab, timeout=30)
    ref.raise_for_status()
    padre = ref.json()["object"]["sha"]
    commit = http.get(f"{API}/repos/{repo}/git/commits/{padre}", headers=cab, timeout=30)
    commit.raise_for_status()
    base_tree = commit.json()["tree"]["sha"]

    arbol = []
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            contenido = base64.b64encode(f.read()).decode()
        blob = http.post(f"{API}/repos/{repo}/git/blobs", headers=cab, timeout=60,
                         json={"content": contenido, "encoding": "base64"})
        blob.raise_for_status()
        arbol.append({
            "path": path.replace("\\", "/"),
            "mode": "100644",
            "type": "blob",
            "sha": blob.json()["sha"],
        })
    if not arbol:
        raise RuntimeError("No hay archivos que subir.")

    tree = http.post(f"{API}/repos/{repo}/git/trees", headers=cab, timeout=30,
                     json={"base_tree": base_tree, "tree": arbol})
    tree.raise_for_status()
    nuevo = http.post(f"{API}/repos/{repo}/git/commits", headers=cab, timeout=30, json={
        "message": mensaje, "tree": tree.json()["sha"], "parents": [padre],
    })
    nuevo.raise_for_status()
    sha = nuevo.json()["sha"]
    movido = http.patch(f"{API}/repos/{repo}/git/refs/heads/{branch}", headers=cab,
                        timeout=30, json={"sha": sha})
    movido.raise_for_status()
    return sha[:7]


def sincronizar(paths, mensaje, secretos=None, token=None, repo=None, branch=None):
    token, repo, branch = _credenciales(secretos, token, repo, branch)
    if not token or not repo:
        return {"ok": False, "detalle": "Falta GITHUB_TOKEN o GITHUB_REPO en Secrets."}
    try:
        sha = subir(paths, mensaje, token, repo, branch)
    except Exception as e:
        return {"ok": False, "detalle": str(e)[:300]}
    return {"ok": True, "detalle": sha}
