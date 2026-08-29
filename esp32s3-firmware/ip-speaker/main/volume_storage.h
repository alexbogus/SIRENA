#pragma once

#include "esp_err.h"

// Persistencia mínima del volumen en NVS (namespace "ipspk_cfg", clave
// "volume"). Adelanto parcial del NVS del Hito 5 (que gestionará también
// credenciales WiFi e IP estática) -- aquí solo se usa para este campo.
// Requiere que nvs_flash_init() ya se haya llamado (lo hace wifi_manager).

// Lee el volumen guardado. Si no hay nada guardado, devuelve `default_volume`.
int volume_storage_load(int default_volume);

// Guarda el volumen. No falla de forma fatal si la escritura falla (se loguea).
void volume_storage_save(int volume_percent);
