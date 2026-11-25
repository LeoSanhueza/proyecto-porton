import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np


CAMERA = "192.168.226.201:554/profile1"
PLATE = re.compile(r"(?:[A-Z]{4}[0-9]{2}|[A-Z]{2}[0-9]{4})", re.ASCII)
OUTPUT = Path("salida")


def plate_from(text):
    candidate = re.sub(r"[ \t.\-]", "", text.strip().upper())
    return candidate if PLATE.fullmatch(candidate) else None


def save_image(path, image):
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"No se pudo codificar {path}.")
    path.write_bytes(encoded.tobytes())


def load_image(path):
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"No se pudo leer la imagen {path}.")
    return image


def crop(frame, zone):
    x, y, w, h = zone
    height, width = frame.shape[:2]
    if x + w > width or y + h > height:
        raise ValueError("La zona excede el tamaño de la imagen. Vuelve a configurarla.")
    return frame[y:y + h, x:x + w]


def validate_zone(zone):
    if (
        not isinstance(zone, (list, tuple))
        or len(zone) != 4
        or any(type(value) is not int for value in zone)
        or min(zone[:2]) < 0
        or min(zone[2:]) <= 0
    ):
        raise ValueError("La zona debe ser X Y ANCHO ALTO en píxeles, con ancho y alto positivos.")
    return zone


def camera_frames(secrets_path, user_override):
    secrets = json.loads(secrets_path.read_text(encoding="utf-8-sig"))
    user = user_override or secrets["usuario"]
    password = secrets["password"]
    if not isinstance(user, str) or not user or not isinstance(password, str) or not password:
        raise ValueError("Configura un usuario y una contraseña en el archivo de secretos.")
    credentials = f"{quote(user, safe='')}:{quote(password, safe='')}"
    address = f"rtsp://{credentials}@{CAMERA}"
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
    os.environ["OPENCV_FFMPEG_DEBUG"] = "0"
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    capture = cv2.VideoCapture()
    try:
        if not capture.open(address, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
        ]):
            raise ValueError("No se pudo abrir RTSP. Revisa la red, el usuario y la contraseña.")
        while True:
            ok, frame = capture.read()
            if not ok:
                raise ValueError("Se perdió el vídeo RTSP. Ejecuta el comando otra vez.")
            yield frame
    except cv2.error:
        raise ValueError("Error de OpenCV al capturar RTSP.") from None
    finally:
        capture.release()


def ocr_engine():
    windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    executable = shutil.which("tesseract")
    if not executable and os.name == "nt" and windows_default.is_file():
        executable = str(windows_default)
    if not executable:
        raise ValueError("Instala Tesseract OCR y agrega su carpeta al PATH.")
    return executable


def read_plate(image, executable):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = max(1, min(3, 100 / gray.shape[0]))
    enlarged = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    if cv2.mean(binary)[0] < 127:
        binary = cv2.bitwise_not(binary)
    bordered = cv2.copyMakeBorder(binary, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    ok, encoded = cv2.imencode(".png", bordered)
    if not ok:
        raise ValueError("No se pudo preparar la imagen para OCR.")
    result = subprocess.run(
        [executable, "stdin", "stdout", "-l", "eng", "--psm", "7",
         "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"],
        input=encoded.tobytes(), capture_output=True, timeout=5, check=False,
    )
    if result.returncode:
        raise ValueError("Tesseract falló. Verifica que esté instalado el idioma eng.")
    return plate_from(result.stdout.decode("utf-8"))


def authorized_plates(path):
    plates = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        plate = plate_from(line)
        if not plate:
            raise ValueError(f"Formato de patente inválido en {path}, línea {number}.")
        plates.add(plate)
    if not plates:
        raise ValueError(f"Agrega al menos una patente a {path}.")
    return plates


def recognize(frames, args, live, zone, allowed, executable):
    previous = None
    count = 0
    last_read = float("-inf")
    last_event = {}
    for frame in frames:
        now = time.monotonic()
        if live and now - last_read < 0.4:
            continue
        if live and now - last_read > 3:
            previous, count = None, 0
        last_read = now
        image = crop(frame, zone)
        plate = read_plate(image, executable)
        if args.ver_lecturas:
            print(f"OCR: {plate or '(sin lectura válida)'}", flush=True)
        if plate not in allowed:
            previous, count = None, 0
            continue
        count = count + 1 if plate == previous else 1
        previous = plate
        if count != args.confirmaciones or now - last_event.get(plate, float("-inf")) < 30:
            continue
        last_event[plate] = now
        timestamp = datetime.now().astimezone()
        mode = "cámara" if live else "prueba con imágenes"
        message = f"{timestamp.isoformat(timespec='seconds')} | Habría abierto | {plate} | {mode}"
        if not args.solo_diario:
            stamp = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            save_image(OUTPUT / f"evento_{stamp}.jpg", frame)
            save_image(OUTPUT / f"evento_{stamp}_zona.jpg", image)
            with (OUTPUT / "eventos.log").open("a", encoding="utf-8") as log:
                log.write(message + "\n")
        print(message, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Reconocimiento de patentes. Simulación de portón.")
    parser.add_argument("--usuario", help="reemplaza el usuario del archivo de secretos")
    parser.add_argument("--secretos", type=Path, default=Path(__file__).resolve().with_name("secretos.json"))
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capturar", help="guarda un fotograma de la cámara")
    setup = commands.add_parser("zona", help="configura la zona sobre una imagen guardada")
    setup.add_argument("imagen", type=Path)
    setup.add_argument("--rect", nargs=4, type=int, metavar=("X", "Y", "ANCHO", "ALTO"))
    run = commands.add_parser("leer", help="reconoce patentes y registra aperturas simuladas")
    run.add_argument("--imagenes", nargs="+", type=Path, help="fotogramas locales en orden")
    run.add_argument("--autorizadas", type=Path, default=Path("autorizadas.txt"))
    run.add_argument("--confirmaciones", type=int, choices=range(2, 11), default=3)
    run.add_argument("--ver-lecturas", action="store_true")
    run.add_argument("--solo-diario", action="store_true",
                     help="envía eventos a la salida estándar sin guardar fotos ni un log propio")
    args = parser.parse_args()

    if args.command == "zona":
        frame = load_image(args.imagen)
        zone = args.rect
        if zone is None:
            height, width = frame.shape[:2]
            scale = min(1, 1200 / width, 750 / height)
            preview = cv2.resize(frame, None, fx=scale, fy=scale)
            window = "Selecciona la zona y pulsa Enter"
            try:
                x, y, w, h = cv2.selectROI(window, preview, showCrosshair=True)
            finally:
                cv2.destroyAllWindows()
            if w == 0 or h == 0:
                print("Selección cancelada.")
                return
            left, top = round(x * width / preview.shape[1]), round(y * height / preview.shape[0])
            right = round((x + w) * width / preview.shape[1])
            bottom = round((y + h) * height / preview.shape[0])
            zone = [left, top, right - left, bottom - top]
        image = crop(frame, validate_zone(zone))
        OUTPUT.mkdir(exist_ok=True)
        save_image(OUTPUT / "zona.jpg", image)
        args.config.write_text(json.dumps({
            "zona": zone, "resolucion": list(frame.shape[:2][::-1]),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Zona guardada en {args.config}. Vista previa: {OUTPUT / 'zona.jpg'}")
        return

    OUTPUT.mkdir(exist_ok=True)
    if args.command == "capturar":
        with_camera = camera_frames(args.secretos, args.usuario)
        try:
            frame = next(with_camera)
        finally:
            with_camera.close()
        path = OUTPUT / f"captura_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
        save_image(path, frame)
        print(f"Imagen guardada en {path}")
        return

    config = json.loads(args.config.read_text(encoding="utf-8"))
    zone = validate_zone(config["zona"])
    allowed = authorized_plates(args.autorizadas)
    executable = ocr_engine()
    live = args.imagenes is None
    if not live and len({path.resolve() for path in args.imagenes}) != len(args.imagenes):
        raise ValueError("Usa archivos de imagen distintos para confirmar la lectura.")
    frames = (camera_frames(args.secretos, args.usuario) if live
              else (load_image(path) for path in args.imagenes))
    try:
        def checked_frames():
            for frame in frames:
                if list(frame.shape[:2][::-1]) != config["resolucion"]:
                    raise ValueError("Cambió la resolución. Configura la zona con una captura de esa resolución.")
                yield frame

        recognize(checked_frames(), args, live, zone, allowed, executable)
    finally:
        frames.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCaptura detenida.")
    except (OSError, ImportError, ValueError, KeyError, TypeError, EOFError,
            subprocess.TimeoutExpired) as error:
        sys.exit(f"Error: {error}")
