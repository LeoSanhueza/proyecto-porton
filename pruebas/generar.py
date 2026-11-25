"""Genera una placa de cartón imprimible y tres escenas de prueba."""

from pathlib import Path

import cv2
import numpy as np


def save(path, image):
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"No se pudo codificar {path}.")
    path.write_bytes(data.tobytes())


def main():
    workspace = Path(__file__).resolve().parents[1]
    output = workspace / "salida" / "banco"
    output.mkdir(parents=True, exist_ok=True)
    plate = np.full((240, 780, 3), 255, np.uint8)
    cv2.rectangle(plate, (8, 8), (771, 231), (0, 0, 0), 5)
    cv2.putText(plate, "KLPF27", (91, 155), cv2.FONT_HERSHEY_SIMPLEX,
                4.7, (0, 0, 0), 9, cv2.LINE_AA)
    save(output / "placa.png", plate)
    for number, (offset, brightness) in enumerate([(0, 255), (3, 210), (-2, 125)], 1):
        frame = np.full((360, 640, 3), brightness // 4, np.uint8)
        small = cv2.resize(plate, (390, 120), interpolation=cv2.INTER_AREA)
        frame[120:240, 125 + offset:515 + offset] = cv2.convertScaleAbs(
            small, alpha=brightness / 255
        )
        save(output / f"escena{number}.png", frame)
    (output / "autorizadas-prueba.txt").write_text("KLPF27\n", encoding="utf-8")
    (output / "autorizadas-negativa.txt").write_text("BCDF12\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
