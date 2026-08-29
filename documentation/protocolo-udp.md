# Protocolo UDP de audio

El altavoz escucha UDP en el **puerto 5005**. Cada datagrama lleva una cabecera propia de 16 bytes (network byte order / big-endian) seguida del payload. Definición canónica en [`../esp32s3-firmware/ip-speaker/main/protocol.h`](../esp32s3-firmware/ip-speaker/main/protocol.h); implementación de referencia en Python en [`../docker/reference_send_audio.py`](../docker/reference_send_audio.py).

## Cabecera (16 bytes)

| Campo | Tipo | Descripción |
|---|---|---|
| `magic` | `uint32` | Siempre `0x53504B31` ("SPK1"). Paquetes con otro valor se descartan. |
| `version` | `uint8` | Siempre `1` actualmente. |
| `frame_type` | `uint8` | `1`=START, `2`=AUDIO, `3`=END, `4`=PING, `5`=PONG |
| `reserved` | `uint16` | Sin uso, reservado para futuros flags. |
| `seq_num` | `uint32` | Número de secuencia incremental dentro del stream (para detectar paquetes perdidos). |
| `payload_len` | `uint32` | Bytes que siguen a la cabecera. |

Formato `struct.pack` en Python: `"!IBBHII"`.

## Tipos de frame

- **`START`** (`payload_len` normalmente 0): inicia un stream nuevo. **Interrumpe inmediatamente** cualquier stream en curso (se vacía el ring buffer) — la alarma más reciente siempre prioriza sobre la que estuviera sonando. El `seq_num` de este frame marca el inicio de la numeración del stream.
- **`AUDIO`**: payload = un frame Opus codificado (20ms, 320 muestras a 16kHz mono). El firmware lo decodifica y lo escribe al ring buffer de reproducción. Si `seq_num` no es el esperado, el hueco se cuenta como paquete(s) perdido(s) y se rellena con **PLC** (Packet Loss Concealment) de Opus en vez de silencio (hasta 25 frames de PLC consecutivos por hueco, ~500ms).
- **`END`** (`payload_len` = 0): marca el fin del stream. El buffer se deja drenar de forma natural (no se vacía), así que el audio ya en tránsito sigue sonando hasta el final.
- **`PING`** (`payload_len` = 0): health-check de red. El firmware responde inmediatamente con un `PONG` (mismo `seq_num`, `payload_len`=0) al remitente.
- **`PONG`**: solo la envía el firmware; si llega uno al firmware se ignora.

## Formato de audio esperado en `AUDIO`

- Origen: PCM 16kHz, mono, 16-bit (el formato que produce Piper TTS).
- Cada bloque de 320 muestras (20ms) se codifica con Opus antes de enviarse.
- Bitrate recomendado: ~24kbps (voz).

## Recomendaciones para el emisor (lección del desarrollo)

Un emisor que envía cada paquete `AUDIO` exactamente al ritmo real-time (20ms entre paquetes, sin ningún margen) produce **audio audiblemente cortado**: en cuanto hay el más mínimo jitter de red, el paquete llega tarde y el altavoz ya se ha quedado sin datos para ese instante. La solución validada en pruebas reales: enviar un **colchón inicial** de ~300ms (los primeros ~15 bloques de 20ms) con un espaciado mínimo (no completamente sin pausa — un burst totalmente instantáneo llegó a saturar el receptor y perder paquetes reales en pruebas) antes de empezar el ritmo real-time. Ver la función `send_stream()` de `docker/reference_send_audio.py` para la implementación de referencia.

## Ejemplo mínimo en Python

```python
import socket, struct

HEADER_FMT = "!IBBHII"
MAGIC = 0x53504B31

def header(frame_type, seq, payload_len):
    return struct.pack(HEADER_FMT, MAGIC, 1, frame_type, 0, seq, payload_len)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dest = ("10.0.1.56", 5005)

sock.sendto(header(1, 0, 0), dest)          # START
# ... enviar N frames AUDIO con seq incremental y payload = frame Opus ...
sock.sendto(header(3, seq_final, 0), dest)  # END
```

Para un caso de uso completo (codificación Opus real, colchón inicial, simulación de pérdida de paquetes con `--simulate-loss`), usar directamente `docker/reference_send_audio.py --host <IP> --wav audio.wav`.

## Health-check / discovery

```python
sock.sendto(header(4, 0, 0), dest)  # PING
data, _ = sock.recvfrom(16)
# data debe decodificar a frame_type=5 (PONG)
```

`docker/reference_send_audio.py --host <IP> --ping` implementa esto.

## Deuda técnica conocida

El protocolo **no lleva autenticación ni verificación de origen** en esta versión (decisión consciente de MVP: seguridad como fase posterior, ver historial de decisiones del proyecto). Cualquier dispositivo en la misma red WiFi podría en teoría enviar audio al altavoz. Pendiente para una fase de endurecimiento: filtro por IP de origen conocida (el servidor Docker) + token/secreto compartido en la cabecera. El mismo razonamiento aplica a los endpoints HTTP `/status` y `/volume` (ver [api-http.md](api-http.md)).
