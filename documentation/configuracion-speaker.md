1. Entra en modo configuración: mantén pulsado el botón BOOT del altavoz mientras le das corriente (o lo reinicias), y déjalo pulsado unos segundos tras el arranque. La comprobación ocurre muy pronto (~50 ms tras iniciar el WiFi), así que asegúrate de tenerlo ya pulsado en el momento del encendido/reset.
2. Conéctate al punto de acceso del altavoz: levanta una red WiFi abierta (sin contraseña) llamada IPSpeaker-Config-XXXX (los 4 últimos caracteres son los 2 últimos bytes de su MAC). Conéctate a ella desde el móvil u ordenador.
3. Abre el portal de configuración: en el navegador, visita http://192.168.4.1/.
4. Rellena el formulario:
   - SSID de la nueva red WiFi (obligatorio)
   - Password (si la red lo requiere)
   - Identificador del altavoz (speaker_id, opcional — útil para saber qué población/zona es)
   - Opcional: IP estática + gateway + máscara, si no quieres DHCP en la red nueva
5. Guarda: el altavoz confirma en pantalla, guarda todo en NVS y se reinicia solo (~1,5 s después) — no hace falta apagarlo/encenderlo manualmente.
6. Tras reiniciar, intentará conectarse a la nueva red (timeout de 15 s). Si conecta, arranca normal (streaming UDP, /status, etc.). Si falla, vuelve a caer solo en modo AP de configuración con el mismo SSID, así que puedes repetir el proceso sin miedo a dejarlo "brickeado".