# Reconocimiento de patentes para el portón

Python 3.13, OpenCV y Tesseract OCR. Esta versión simula la apertura. Cuando la
misma patente autorizada aparece en tres lecturas consecutivas, escribe
`Habría abierto` en `salida/eventos.log` y guarda el fotograma y el recorte
correspondientes. Una lectura vacía, inválida o de otra patente interrumpe la
confirmación. Hay un intervalo mínimo de 30 segundos entre eventos de la misma
patente y un solo evento por racha continua de lecturas.

Se admiten los formatos chilenos de auto de cuatro letras y dos números
(`BCDF12`) y de dos letras y cuatro números (`AB1234`). La comparación es
exacta después de quitar espacios, guiones y puntos. La zona es fija y el OCR
busca una línea de texto, así que conviene que el vehículo se detenga en un punto
predecible y que la zona enmarque de cerca los caracteres.

## Windows

Ejecuta los comandos desde la carpeta del proyecto en PowerShell. Si falta
`.venv`, créalo con `py -3.13 -m venv .venv` después de instalar
[Python 3.13 de 64 bits](https://www.python.org/downloads/windows/).

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item autorizadas.ejemplo.txt autorizadas.txt
notepad autorizadas.txt
```

Reemplaza las dos patentes de ejemplo por las tuyas, una por línea. Si ya
tienes una lista, conserva tu archivo. Instala [Tesseract OCR para Windows](https://tesseract-ocr.github.io/tessdoc/Installation#windows)
con el idioma inglés (`eng`). El programa lo busca en el PATH y en
`C:\Program Files\Tesseract-OCR\tesseract.exe`. Para revisar esa instalación,
ejecuta `& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --list-langs`.

Con la cámara TVT TD-9521S4H encendida y conectada al Ethernet con
`192.168.226.10/24`, comprueba el acceso RTSP y guarda una captura. Coloca un
auto en el punto de lectura antes de capturar.

```powershell
Test-NetConnection 192.168.226.201 -Port 554
.\.venv\Scripts\python.exe porton.py --usuario admin capturar
```

Usa el mismo usuario que en VLC si difiere de `admin`. El programa se conecta
por TCP a `rtsp://192.168.226.201:554/profile1`. Tanto `capturar` como `leer`
en vivo buscan `secretos.json` junto a `porton.py`. En una instalación nueva,
crea ese archivo localmente con los campos `usuario` y `password`.
`--secretos RUTA` permite indicar otra ubicación antes del subcomando.
El archivo está excluido de Git. Si alguna versión previa con la contraseña
incrustada llegó a publicarse, cambia la contraseña de la cámara.

```powershell
$captura = Get-ChildItem salida\captura_*.jpg | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\.venv\Scripts\python.exe porton.py zona $captura.FullName
.\.venv\Scripts\python.exe porton.py --usuario admin leer --ver-lecturas
```

Arrastra un rectángulo alrededor de los caracteres y pulsa Enter. Revisa
`salida/zona.jpg` y repite `zona` si aparecen otros textos o se cortan caracteres.
La selección se guarda en `config.json`, junto con la resolución. Repite la
selección si cambias el encuadre o la resolución. Detén el lector con Ctrl+C.

## Prueba con fotos

### Banco de pruebas sin cámara ni autos

Genera una placa ficticia y tres escenas con distinto brillo.

```powershell
.\.venv\Scripts\python.exe pruebas/generar.py
.\.venv\Scripts\python.exe porton.py --config salida/banco/zona.json zona salida/banco/escena1.png --rect 162 140 308 70
.\.venv\Scripts\python.exe porton.py --config salida/banco/zona.json leer --autorizadas salida/banco/autorizadas-prueba.txt --imagenes salida/banco/escena1.png salida/banco/escena2.png salida/banco/escena3.png --ver-lecturas
```

El resultado esperado es un evento `Habría abierto` para `KLPF27`. Repite
usando `salida/banco/autorizadas-negativa.txt`. Debe mostrar las lecturas
sin añadir otro evento. Estas pruebas requieren Tesseract con `eng`.

Imprime `salida/banco/placa.png` en papel mate, en horizontal, con un ancho
aproximado de 30 cm. Pégala a un cartón y colócala sobre un soporte a la altura
y distancia de una patente real. Cuando montes la cámara, prueba ese objeto
de día y de noche con el accionamiento del portón desconectado del lector.
Usa una lista de prueba separada. El banco de imágenes permite ensayar el OCR,
pero carece de los reflejos, el movimiento y la iluminación de la instalación.

### Prueba con capturas de la cámara

Guarda tres fotogramas distintos de la misma patente en la posición de lectura
y con la misma resolución de la foto usada para definir la zona. Puedes
obtenerlos con tres ejecuciones de `capturar`. Sustituye las rutas de este ejemplo
por tus archivos, en orden de captura.

```powershell
.\.venv\Scripts\python.exe porton.py leer --imagenes foto1.jpg foto2.jpg foto3.jpg --ver-lecturas
Get-Content salida\eventos.log -Tail 10
```

La prueba con imágenes funciona sin conexión ni contraseña. Comprueba que tres
lecturas consecutivas de una patente autorizada produzcan un evento marcado
`prueba con imágenes`. Repite con una patente fuera de la lista y comprueba que
no se agregue un evento. En vivo, verifica ambas pruebas antes de confiar en
los resultados. Si el OCR falla, revisa el recorte, los reflejos, el enfoque y
la posición del auto.

## Debian en el Advantech AIMC-2000

Estos comandos corresponden a Debian 13 (Trixie). En el AIMC-2000 comprueba
`dpkg --print-architecture` y usa el mismo Debian y arquitectura en el equipo
que prepara los paquetes. Para el AIMC-2000 con Celeron J1900, el objetivo es
Debian `amd64`. Copia por USB `porton.py`, `requirements-debian.txt`,
`porton.service`, `autorizadas.txt`, `config.json` y `secretos.json`. Crea un entorno virtual
nuevo en Debian.

### Preparación sin Internet en el Advantech

En una máquina o VM con Internet, parte de la misma imagen base y del mismo
estado de paquetes que tiene el Advantech. Desde una carpeta con
`requirements-debian.txt`, descarga los paquetes y sus dependencias pendientes.

```bash
mkdir -p paquete/debs/partial paquete/wheels
sudo apt-get update
sudo apt-get -o "Dir::Cache::archives=$PWD/paquete/debs" --download-only install python3.13-venv tesseract-ocr tesseract-ocr-eng
python3.13 -m pip download --only-binary=:all: -r requirements-debian.txt -d paquete/wheels
```

Para ejecutar la última línea, usa un entorno con Python 3.13 y pip en la
máquina conectada. Instálalos allí después de descargar los paquetes Debian
si hacen falta. Copia la carpeta `paquete` junto al programa por USB. Instala
desde la copia local en el AIMC-2000.

```bash
sudo apt-get --no-download install ./paquete/debs/*.deb
python3.13 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links paquete/wheels -r requirements-debian.txt
tesseract --list-langs
```

El listado debe incluir `eng`. Si APT indica una dependencia ausente,
compara el estado de los paquetes de origen y destino antes de preparar
otra copia. Verifica el paquete completo en una VM desconectada antes de
llevarlo al Advantech.

Configura la interfaz conectada a la cámara con una IP libre de
`192.168.226.0/24`, por ejemplo `192.168.226.11/24` si está libre. Si Debian
y Windows están conectados al mismo tiempo, usa una IP diferente en cada equipo.
Comprueba la ruta a la cámara, captura una imagen y ejecuta el lector desde la
carpeta del proyecto.

```bash
ip route get 192.168.226.201
.venv/bin/python porton.py --usuario admin capturar
.venv/bin/python porton.py --usuario admin leer --ver-lecturas
```

Si necesitas ajustar la zona sin escritorio, abre la captura en otro equipo
para identificar las coordenadas en píxeles. Aplica el rectángulo desde Debian
con `zona` y `--rect`, en orden X, Y, ancho y alto desde la esquina superior
izquierda. Cambia el nombre del archivo y los valores por los tuyos.

```bash
.venv/bin/python porton.py zona salida/captura_FECHA.jpg --rect 700 420 320 100
```

### Arranque automático con systemd

Cuando funcione la prueba manual, instala los archivos y crea el entorno
virtual definitivo en `/opt/porton`. Ejecuta el bloque desde la copia local
del proyecto en Debian.

```bash
id porton >/dev/null 2>&1 || sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin porton
sudo install -d -o root -g porton -m 0750 /opt/porton
sudo install -o root -g porton -m 0640 porton.py config.json autorizadas.txt secretos.json requirements-debian.txt /opt/porton/
sudo python3.13 -m venv /opt/porton/.venv
sudo /opt/porton/.venv/bin/python -m pip install --no-index --find-links "$PWD/paquete/wheels" -r /opt/porton/requirements-debian.txt
sudo install -m 0644 porton.service /etc/systemd/system/porton.service
sudo systemd-analyze verify /etc/systemd/system/porton.service
sudo systemctl daemon-reload
sudo systemctl enable --now porton.service
sudo systemctl status porton.service
sudo journalctl -u porton.service -f
```

El servicio arranca con Debian y reintenta cada diez segundos si termina,
por ejemplo cuando la cámara pierde la conexión o tarda en encender.
Registra los eventos en el diario de systemd. Para evitar acumular
fotogramas en funcionamiento continuo, las imágenes se guardan durante las
pruebas ejecutadas manualmente. Si cambias las patentes autorizadas o la
zona, actualiza los archivos en `/opt/porton` y reinicia el servicio con
`sudo systemctl restart porton.service`.

Prueba un reinicio del Advantech y una desconexión y reconexión de la cámara.
Si también quieres que el AIMC se encienda solo después de un corte eléctrico,
comprueba si su BIOS permite restaurar el encendido al volver la corriente.

### Actualización automática desde GitHub

Esta opción requiere acceso saliente a Internet desde Debian. Usa un
repositorio público con publicaciones estables y control de quién puede
publicar. El actualizador instala solo `porton.py` en una instalación
existente. Conserva los secretos, las patentes, la zona, la unidad systemd
y el entorno Python. Un cambio de dependencias o del servicio requiere
instalación manual. El servicio de lectura puede seguir funcionando con
la versión local si GitHub o Internet no están disponibles.

Antes de publicar, comprueba que el historial y los archivos de la publicación
estén libres de contraseñas, patentes y capturas. Publica una versión estable
con estos **dos archivos adjuntos**. En Debian puedes generar el segundo con
`sha256sum porton.py > porton.py.sha256`. Publica ambos juntos.

- `porton.py`
- `porton.py.sha256`

En el AIMC, instala las unidades y crea la configuración con el repositorio
real. Si usas un repositorio privado, este actualizador necesitará soporte
de autenticación antes de activarlo.

```bash
sudo install -d -m 0755 /etc/porton
sudoedit /etc/porton/actualizacion.json
sudo install -o root -g root -m 0644 actualizar.py /opt/porton/
sudo install -m 0644 porton-actualizar.service porton-actualizar.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start porton-actualizar.service
sudo journalctl -u porton-actualizar.service -n 20
sudo systemctl enable --now porton-actualizar.timer
```

Contenido de ejemplo de `actualizacion.json`:

```json
{"repositorio": "propietario/nombre"}
```

El temporizador comprueba la última publicación estable cada 15 minutos.
El actualizador verifica el SHA-256 y la sintaxis antes de sustituir el archivo
y reiniciar el lector. Si la versión se instala pero el reconocimiento
empeora, detén el temporizador y restaura la copia anterior.

```bash
sudo systemctl disable --now porton-actualizar.timer
sudo install -o root -g porton -m 0640 /opt/porton/porton.py.anterior /opt/porton/porton.py
sudo systemctl restart porton.service
```

### Pruebas de los dos autos

Registra las dos patentes completas en `autorizadas.txt`. Usa la coincidencia
exacta de patente para identificar cada auto. El modelo puede servir como
comprobación adicional si las pruebas muestran que aporta valor. Dos autos
distintos del mismo modelo siguen siendo indistinguibles por el modelo.

Prueba cada auto de día, de noche con faros encendidos y de noche con faros
apagados. Repite con un auto ajeno. Anota cuántas llegadas se detectan, cuánto
tarda la confirmación y si hay lecturas o eventos erróneos. Inspecciona
`salida/zona.jpg` antes de ajustar OCR. Si los caracteres aparecen quemados
o borrosos, ajusta primero el encuadre, el enfoque y la exposición o la
iluminación de la placa. El servicio instalado en esta fase registra
`Habría abierto`. La integración física depende de la central del portón y
de cómo se acciona su entrada de apertura.

Referencias de instalación para [OpenCV de escritorio](https://pypi.org/project/opencv-python/5.1.0.95/),
[OpenCV sin escritorio](https://pypi.org/project/opencv-python-headless/5.1.0.95/) y
[Python 3.13 en Debian 13](https://packages.debian.org/trixie/python3.13-venv).
Consulta también la documentación de [descarga de paquetes de pip](https://pip.pypa.io/en/stable/cli/pip_download/)
y de [directorios administrados por systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
