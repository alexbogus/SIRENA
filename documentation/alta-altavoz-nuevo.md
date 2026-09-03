# Alta de un altavoz nuevo — guía paso a paso

Proceso completo para poner en marcha un altavoz ESP32-S3 nuevo y darlo de alta en **SIRENA** (el centro de mando), desde que sale de la caja hasta que ya recibe alertas automáticas del feed 112CV.

## 1. Flashear el firmware

Este es el primer paso obligatorio en cualquier altavoz nuevo: hasta que no tiene firmware cargado no existe portal AP ni nada que configurar. Desde `esp32s3-firmware/ip-speaker/` (ver [setup.md](setup.md) para el detalle de instalación del entorno ESP-IDF):

```bash
source /Users/alexcasanova/.espressif/tools/activate_idf_v6.1.sh
cd esp32s3-firmware/ip-speaker
```

`main/wifi_credentials.h` (gitignored) debe existir antes de compilar por primera vez — si el repo es nuevo en tu máquina, créalo a partir del ejemplo:

```bash
cp main/wifi_credentials.h.example main/wifi_credentials.h  # rellena SSID/password de tu red de desarrollo
```

Estas credenciales son solo un **fallback de compilación**: en el primer arranque de un altavoz nuevo (NVS vacía, sin `speaker_id` ni WiFi guardados) el firmware las usa para intentar conectarse por STA a esa red — no hace falta pulsar nada para que arranque. Solo hace falta el portal AP (paso 2) si:
- quieres configurar directamente la red/zona definitiva sin pasar por la red de desarrollo, o
- esa red de desarrollo no es alcanzable desde donde estás flasheando/probando, o
- `wifi_credentials.h` no tiene SSID válido.

En cualquiera de esos casos, fuerza el modo AP manteniendo pulsado el botón **BOOT** durante el arranque/reset (ver paso 2).

Compila:

```bash
idf.py build
```

Si tienes varios dispositivos USB conectados y no sabes cuál es el altavoz nuevo, identifica su puerto por diferencia (conéctalo *después* del primer `ls`):

```bash
ls /dev/cu.* > /tmp/ports-before.txt
# conecta el altavoz nuevo por USB
ls /dev/cu.* > /tmp/ports-after.txt
diff /tmp/ports-before.txt /tmp/ports-after.txt
```

Flashea y abre el monitor serie en el mismo comando para ver el arranque completo:

```bash
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

En un altavoz **totalmente nuevo** (flash de fábrica, nunca antes programado con este firmware) no hace falta borrar la flash a mano — `idf.py flash` escribe bootloader, tabla de particiones y app; la partición NVS parte vacía y el firmware la inicializa solo en el primer arranque. Solo recurre a un borrado completo si vienes de reflashear un altavoz que traía **otro** firmware o una tabla de particiones incompatible:

```bash
idf.py -p /dev/cu.usbmodemXXXX erase-flash
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

En el log del monitor, tras el arranque de componentes (I2C, codec ES8311, I2S) deberías ver el intento de conexión WiFi. Si usa las credenciales de `wifi_credentials.h` y conecta, el altavoz arranca ya en modo normal (streaming UDP, `/status`, etc.) — en ese caso puedes usarlo así en modo desarrollo, pero para dejarlo operativo en su red/zona definitiva sigue con el paso 2. Sal del monitor con `Ctrl+]`.

## 2. Configurar WiFi y `speaker_id` vía portal de configuración

Detalle completo en [configuracion-speaker.md](configuracion-speaker.md). Resumen:

1. Arranca (o resetea) el altavoz manteniendo pulsado el botón **BOOT**. La comprobación ocurre ~50 ms tras iniciar el WiFi, así que tiene que estar pulsado ya en el momento del encendido/reset.
2. Conéctate desde tu móvil/portátil a la red abierta `IPSpeaker-Config-XXXX` que crea el propio altavoz (los 4 últimos caracteres son los 2 últimos bytes de su MAC).
3. Abre `http://192.168.4.1/` en el navegador.
4. Rellena el formulario: SSID de la red definitiva (obligatorio), password, `speaker_id` (opcional, identifica población/zona) y, si no quieres DHCP, IP estática + gateway + máscara.
5. Guarda: el altavoz confirma en pantalla, persiste todo en NVS y se reinicia solo (~1,5 s) sin intervención manual.
6. Tras reiniciar intenta conectarse a la red nueva (timeout 15 s). Si falla, vuelve a caer en modo AP con el mismo SSID — no hay riesgo de dejarlo inservible, se puede repetir el proceso.

## 3. Comprobar que el altavoz está operativo

Con el altavoz ya en la red definitiva, comprueba su endpoint de estado (documentado en [api-http.md](api-http.md)):

```bash
curl http://<IP_DEL_ALTAVOZ>/status
```

Debe devolver JSON con `firmware_version`, `ip`, `mac`, `rssi`, `state` (`idle`/`streaming`), `volume` y `uptime`. Anota la IP (y opcionalmente la MAC) — las necesitarás en el siguiente paso.

Opcionalmente, prueba audio directo antes de integrarlo en SIRENA:

```bash
pip install opuslib   # + libopus del sistema (brew install opus / apt install libopus0)
python3 docker/reference_send_audio.py --host <IP_DEL_ALTAVOZ> --wav audio_16k_mono.wav
```

## 4. Dar de alta el altavoz en SIRENA

En el dashboard (`docker/dashboard/`), sección **Altavoces** (`/speakers/`):

1. Rellena el formulario de alta: **nombre** e **IP** son obligatorios; **puerto** (por defecto `5005`, el puerto UDP del protocolo de audio — ver [protocolo-udp.md](protocolo-udp.md)); **zonas** a las que pertenece (multiselección, opcional); **descripción** libre (opcional).
2. Al guardar, el altavoz queda **habilitado** por defecto — solo los altavoces habilitados reciben envíos automáticos y manuales.
3. El campo `speaker_id` que configuraste en el firmware (paso 2) es solo informativo para ti al identificar el hardware — SIRENA no lo lee directamente; el vínculo entre el registro de la base de datos y el hardware real es la **IP** (y, una vez empieza a hacer polling, la **MAC** reportada por `/status`).
4. Tras el alta, el job de fondo `services/status_poller.py` empieza a consultar `GET /status` periódicamente y rellena en la ficha del altavoz: versión de firmware, MAC real, RSSI, estado, volumen y últimos timestamps. Si el polling falla repetidamente, revisa que la IP sea correcta y que el altavoz esté en la misma red/alcanzable desde el contenedor `dashboard` (`network_mode: host`).

Si el altavoz pertenece a una **zona** que ya existía (población/área con otros altavoces), añádelo a esa zona en el propio formulario de alta o edítalo después — así queda cubierto tanto por alertas automáticas de zona como por envíos manuales a esa zona.

## 5. Verificación final

- Desde **Altavoces**, comprueba que el estado que reporta el polling es `idle` (no `streaming`) y que el RSSI/volumen tienen valores razonables.
- Haz un envío manual de prueba desde SIRENA (mensaje de texto → TTS → audio al altavoz) y confirma que se escucha correctamente y que la ficha del altavoz registra la entrega (`services/delivery_confirmation.py`).
- Si el altavoz cubre una zona con reglas de alerta automática activas sobre el feed 112CV, verifica en `/rules` que la zona está incluida en las reglas correspondientes.

Con esto el altavoz queda operativo: recibe tanto envíos manuales como alertas automáticas del feed 112CV para su zona.
