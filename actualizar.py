"""Instala el porton.py de la última publicación estable de GitHub."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen


ROOT = Path("/opt/porton")
PROGRAM = ROOT / "porton.py"
PREVIOUS = ROOT / "porton.py.anterior"
SETTINGS = Path("/etc/porton/actualizacion.json")


def download(url, limit):
    with urlopen(url, timeout=20) as response:
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("El archivo de la publicación tiene un tamaño inválido.")
    return data


def replace_file(path, data, permissions):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temporary_path = Path(temp.name)
    try:
        temporary_path.write_bytes(data)
        os.chown(temporary_path, permissions.st_uid, permissions.st_gid)
        os.chmod(temporary_path, permissions.st_mode & 0o777)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main():
    repository = json.loads(SETTINGS.read_text(encoding="utf-8"))["repositorio"]
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("Indica el repositorio como propietario/nombre.")
    base = f"https://github.com/{repository}/releases/latest/download"
    expected = download(f"{base}/porton.py.sha256", 1024).decode("ascii").strip().split()[0]
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", expected):
        raise ValueError("La publicación no trae un SHA-256 válido.")
    current = PROGRAM.read_bytes()
    if hashlib.sha256(current).hexdigest() == expected.lower():
        print("La versión publicada ya está instalada.")
        return
    candidate = download(f"{base}/porton.py", 1024 * 1024)
    if hashlib.sha256(candidate).hexdigest() != expected.lower():
        raise ValueError("El archivo descargado no coincide con su SHA-256.")
    compile(candidate, str(PROGRAM), "exec")
    permissions = PROGRAM.stat()
    replace_file(PREVIOUS, current, permissions)
    replace_file(PROGRAM, candidate, permissions)
    try:
        subprocess.run(["systemctl", "try-restart", "porton.service"], check=True)
    except subprocess.CalledProcessError:
        replace_file(PROGRAM, current, permissions)
        subprocess.run(["systemctl", "start", "porton.service"], check=False)
        raise
    print("Actualización instalada. La versión anterior quedó en porton.py.anterior.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, SyntaxError, IndexError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f"Actualización fallida: {error}")
