# Enviar avisos por megafonía desde n8n vía API — guía paso a paso

Cómo conectar el workflow de n8n **"ALERTAS CCE - COMDES"** (que resume los
boletines del 112CV/CCE y ya tiene una caja "TTS para Megafonía IP" con el
texto listo para voz, pero sin salida conectada) con la API de SIRENA
(`POST /api/v1/announce`), para que ese texto se sintetice y se reproduzca
automáticamente por los altavoces IP.

No hace falta tocar el JSON exportado del workflow ni el código de SIRENA:
todo se hace desde la UI de n8n y desde **Configuración** del dashboard.

## 0. Requisitos previos

- El dashboard SIRENA tiene que ser alcanzable en red desde la instancia de
  n8n (misma LAN/VPN — la API no lleva más protección que el token, ver
  [api-http.md](api-http.md) para el mismo tipo de decisión ya tomada con
  los endpoints del propio altavoz).
- Al menos una **zona** y un **altavoz** ya dados de alta en SIRENA (ver
  [alta-altavoz-nuevo.md](alta-altavoz-nuevo.md)) — el token que vas a
  crear en el paso 1 se puede restringir a zonas concretas, así que
  conviene tenerlas creadas antes.

## 1. Crear el token de API en SIRENA

1. Entra en el dashboard → **Configuración** → pestaña **"Tokens de API"**.
2. Rellena el formulario de creación:
   - **Nombre**: identifica de un vistazo quién usa el token, por ejemplo
     `n8n-cce`. No tiene que ser único, es solo para reconocerlo en la
     lista.
   - **Zonas permitidas**: déjalo vacío si este token debe poder avisar a
     *cualquier* zona/altavoz del sistema (equivalente al envío manual).
     Si prefieres limitarlo por mínimo privilegio (recomendado si el
     origen del aviso solo cubre una zona/población concreta), selecciona
     una o varias zonas en el desplegable.
3. Pulsa **Crear token**. El valor completo del token (con el prefijo
   `sirena_...`) aparece **una sola vez**, en el mensaje de confirmación.
   Cópialo ahora mismo a un gestor de contraseñas o directamente al
   credential de n8n del paso 3 — SIRENA no lo vuelve a mostrar (solo se
   guarda el hash), y si lo pierdes la única opción es borrar el token y
   crear uno nuevo.
4. La fila del token en la lista muestra su estado (activo/revocado), las
   zonas asignadas, fecha de creación y último uso — últil para confirmar
   más adelante que n8n lo está usando de verdad.

> Para revocar el acceso en cualquier momento (por ejemplo si se filtra el
> token o cambia el proveedor), usa el botón **Revocar** de esa misma fila
> — no hace falta borrarlo ni redesplegar nada; una petición con un token
> revocado devuelve `401` de inmediato.

## 2. Localizar los ids/nombres de zona y altavoz (si vas a apuntar a uno concreto)

Si vas a dirigir el aviso a **una zona o altavoz concreto** en vez de a
"todas las zonas permitidas al token", necesitas su identificador o su
nombre exacto:

- **Zonas**: `/zones/` — cada fila muestra el nombre y, justo al lado, su
  id (`#N`).
- **Altavoces**: `/speakers/` — igual, id junto al nombre en la columna
  "Dispositivo".
- **Tonos** (opcional, solo si quieres forzar un preámbulo sonoro distinto
  del que está marcado por defecto): Configuración → pestaña "Tonos" — id
  junto al nombre de cada tono.

La API acepta **tanto el id numérico como el nombre exacto** (case
insensitive) para zonas, altavoces y tono — usa lo que te resulte más
cómodo de mantener en el nodo de n8n. Usar el **nombre** es más legible en
el JSON del workflow y no se rompe si algún día se borra y se vuelve a
crear la zona con otro id; usar el **id** es marginalmente más rápido (se
salta la búsqueda por nombre) y es la única opción si dos zonas/altavoces
llegaran a compartir nombre.

## 3. Añadir el nodo HTTP Request en n8n

1. Abre el workflow **"ALERTAS CCE - COMDES"** en n8n.
2. Añade un nodo **HTTP Request** nuevo, conectado a la salida de la caja
   **"TTS para Megafonía IP"** (esa caja ya deja el texto listo para voz en
   `{{ $json.response.text }}` — es la misma variable que usan el resto de
   ramas del workflow, como "Envio a API CECOM" o "Envio a API MESHCORE").
3. Configura el nodo:
   - **Method**: `POST`
   - **URL**: `http://<host-sirena>:8080/api/v1/announce`
     (sustituye `<host-sirena>` por la IP o nombre de host del VPS/servidor
     donde corre el contenedor `dashboard`; puerto `8080` salvo que se haya
     cambiado en `docker-compose.yml`).
   - **Authentication**: ninguna gestionada por n8n — el token va en una
     cabecera manual (siguiente punto). Si prefieres no pegar el token en
     claro dentro del nodo, créate una **Credential → Header Auth** en n8n
     con `Name: Authorization` y `Value: Bearer sirena_...`, y selecciónala
     en el nodo en vez de la cabecera manual.
   - **Send Headers** → activar, y añadir:
     - `Authorization`: `Bearer <token copiado en el paso 1>`
     - `Content-Type`: `application/json`
   - **Send Body** → activar, **Body Content Type**: `JSON`, y pega el
     cuerpo según el destino que quieras (ver paso 4).

## 4. Cuerpo de la petición según el destino

El campo `text` es siempre el mismo (`={{ $json.response.text }}`); lo que
cambia es `target` y el campo que lo acompaña.

**A una zona concreta, por nombre** (recomendado, más legible):
```json
{
  "text": "={{ $json.response.text }}",
  "target": "zone",
  "zone_names": ["CECOM"]
}
```

**A una zona concreta, por id:**
```json
{
  "text": "={{ $json.response.text }}",
  "target": "zone",
  "zone_ids": [3]
}
```

**A varias zonas a la vez** (combina `zone_names`/`zone_ids`, y también
entre sí si hace falta):
```json
{
  "text": "={{ $json.response.text }}",
  "target": "zone",
  "zone_names": ["CECOM", "Cocina"]
}
```

**A un altavoz concreto** (por nombre o id, igual que las zonas):
```json
{
  "text": "={{ $json.response.text }}",
  "target": "speaker",
  "speaker_names": ["Recepción"]
}
```

**A todas las zonas que el token tenga permitidas** (o a *todos* los
altavoces del sistema, si el token no tiene restricción de zona):
```json
{
  "text": "={{ $json.response.text }}",
  "target": "all"
}
```

**Forzando un tono de preámbulo distinto del que está marcado por defecto**
(opcional, añade `tone_id` o `tone_name` a cualquiera de los cuerpos
anteriores):
```json
{
  "text": "={{ $json.response.text }}",
  "target": "zone",
  "zone_names": ["CECOM"],
  "tone_name": "Urgente"
}
```

> Si el token está restringido a unas zonas concretas (paso 1) y el cuerpo
> pide una zona o altavoz **fuera** de ese alcance, la API responde `403`
> sin llegar a sintetizar ni enviar nada — ver la tabla de errores del
> paso 6.

## 5. Comportamiento si el altavoz ya está reproduciendo algo

A diferencia del envío manual desde el propio dashboard (que siempre
interrumpe lo que esté sonando — pensado para alertas de emergencia donde
"la más nueva gana"), los mensajes que llegan por esta API **se encolan**
para cualquier altavoz que en ese momento ya esté reproduciendo otra cosa,
y se reproducen automáticamente en cuanto ese altavoz queda libre. Si el
altavoz sigue ocupado más allá del tiempo configurado en Configuración →
"Cola de mensajes de la API" (5 minutos por defecto), el mensaje encolado
se descarta y queda registrado como error (ver siguiente paso). No hace
falta ninguna configuración adicional en n8n para esto — es automático por
altavoz.

## 6. Probar el nodo y verificar

1. En n8n, ejecuta el nodo HTTP Request de forma manual (botón "Execute
   node" / "Test step") con una entrada de ejemplo, o dispara una
   ejecución completa del workflow.
2. La respuesta esperada con `200 OK` tiene esta forma:
   ```json
   { "message_id": 42, "dispatched": [5], "queued": [] }
   ```
   - `dispatched`: ids de los altavoces a los que se envió de inmediato.
   - `queued`: ids de los que estaban ocupados y quedaron en cola (ver
     paso 5).
3. Comprueba en el dashboard SIRENA:
   - **Panel principal** → el altavoz destino debe mostrar el mensaje como
     "Último mensaje enviado" (o quedar en cola, si estaba ocupado).
   - **Mensajes enviados** (`/messages/history`) → debe aparecer con
     origen **"vía API (nombre del token)"**.
   - Configuración → "Tokens de API" → el token usado debe actualizar su
     columna "Último uso".

### Errores más comunes

| HTTP | Causa | Qué revisar |
|---|---|---|
| `400` | Falta `text`, `target` no es `all`/`zone`/`speaker`, o un nombre de zona/altavoz/tono no existe. | El cuerpo JSON del nodo; revisa que el nombre coincide exactamente con el de `/zones/`, `/speakers/` o la pestaña de tonos. |
| `401` | Falta la cabecera `Authorization`, el token está mal copiado, o ha sido **revocado**/borrado. | El header del nodo HTTP Request, y el estado del token en Configuración. |
| `403` | El token está restringido a unas zonas y el destino pedido cae fuera de ese alcance. | O amplías las zonas permitidas del token, o ajustas `zone_ids`/`zone_names`/`speaker_ids`/`speaker_names` del nodo a algo dentro de su alcance. |
| `502` | Fallo al sintetizar el audio (el sidecar `piper` no responde). | Estado del contenedor `piper` en el VPS (`docker compose ps`, `docker compose logs piper`); no es un problema del nodo de n8n. |

Con esto el aviso generado por "TTS para Megafonía IP" queda conectado de
extremo a extremo: n8n → API de SIRENA → síntesis TTS → megafonía IP,
sin tocar el resto del workflow existente (SDS, CECOM, MESHCORE siguen
funcionando igual, en paralelo).
