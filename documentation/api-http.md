# API HTTP

El altavoz expone dos servidores HTTP distintos, **nunca ambos a la vez** (evitan competir por el puerto 80):

- **Modo normal (STA, conectado a la red real)**: `http_status_server` — status y control de volumen.
- **Modo AP de configuración** (sin credenciales válidas, fallo de conexión, o botón BOOT mantenido en el arranque): `http_config_server` — portal para configurar WiFi.

## Modo normal: status y control (`http_status_server.c`)

Disponible en `http://<IP_DEL_ALTAVOZ>/` (puerto 80) mientras el altavoz está conectado a la red normal.

### `GET /status`

```bash
curl http://10.0.1.56/status
```

```json
{
  "firmware_version": "0.2.0",
  "ip": "10.0.1.56",
  "mac": "A0:F2:62:E3:46:F8",
  "rssi_dbm": -32,
  "state": "idle",
  "volume_percent": 70,
  "last_message_at": "29/08/2026 - 13:49:56",
  "last_healthcheck_at": "29/08/2026 - 13:49:56",
  "uptime_seconds": 171
}
```

| Campo | Descripción |
|---|---|
| `firmware_version` | Versión compilada (`main/firmware_version.h`), a subir a mano en cada release relevante. |
| `ip` | IP actual del altavoz. |
| `mac` | MAC de la interfaz WiFi STA (`esp_wifi_get_mac`), formateada `AA:BB:CC:DD:EE:FF`. Usada por el dashboard para identificar el hardware físico más allá del nombre/IP asignados. |
| `rssi_dbm` | Nivel de señal WiFi. |
| `state` | `"idle"` o `"streaming"` — refleja el estado **real** de la máquina de estados del protocolo (`udp_audio_server_is_streaming()`), no una estimación por ocupación del buffer. |
| `volume_percent` | Volumen actual (0-100), persistido en NVS. |
| `last_message_at` | Timestamp del último frame `START`/`AUDIO` recibido, o `null` si no se ha recibido ninguno desde el arranque. |
| `last_healthcheck_at` | Hora actual del dispositivo en el momento de esta petición — útil también para verificar indirectamente que la sincronización SNTP funciona (si aparece muy desfasada, es señal de fallo de sincronización). |
| `uptime_seconds` | Segundos desde el arranque. |

Los timestamps requieren que el dispositivo haya sincronizado su reloj por SNTP tras conectar (ver `time_sync.c`); si aún no ha sincronizado, salen como `null`.

### `POST /volume`

```bash
curl -X POST http://10.0.1.56/volume -H "Content-Type: application/json" -d '{"volume_percent": 70}'
```

Ajusta el registro de ganancia del ES8311 (0-100) y lo persiste en NVS (sobrevive a reinicios). Respuesta: `{"volume_percent": 70}`.

## Modo AP: portal de configuración (`http_config_server.c`)

Cuando el altavoz no puede conectar a la red configurada (o no tiene ninguna), levanta un punto de acceso WiFi **abierto** llamado `IPSpeaker-Config-XXXX` (XXXX = últimos 2 bytes de la MAC). Conéctate a esa red desde un móvil/portátil y visita `http://192.168.4.1/`.

El formulario (`GET /`) permite indicar:
- SSID y contraseña de la red WiFi real.
- Identificador legible del altavoz (`speaker_id`, opcional — p.ej. el nombre de la población/zona).
- IP estática opcional (con máscara y puerta de enlace) o dejar DHCP.

Al enviarlo (`POST /save`, `application/x-www-form-urlencoded`), la configuración se guarda en NVS y el dispositivo se reinicia automáticamente para aplicarla. Si las nuevas credenciales no funcionan, el altavoz vuelve a caer en modo AP de configuración en el siguiente intento fallido.

Para forzar el modo de configuración manualmente en un altavoz ya desplegado (sin borrar la NVS): mantener pulsado el **botón BOOT** durante el arranque.

## Deuda técnica conocida

Ninguno de estos endpoints (`/status`, `/volume`, ni el portal en modo AP) lleva autenticación en esta versión — decisión consciente de MVP (seguridad como fase posterior). Cualquier dispositivo en la misma red podría leer el estado, cambiar el volumen, o (en modo AP) reconfigurar el altavoz. Ver también la nota de deuda técnica en [protocolo-udp.md](protocolo-udp.md).
