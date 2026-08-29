#pragma once

#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>

// Configuración persistida en NVS (namespace "ipspk_cfg", igual que
// volume_storage.c) para no tener que reflashear cada altavoz al
// desplegar varias unidades: credenciales WiFi + IP estática opcional.

typedef struct {
    char ssid[33];       // hasta 32 caracteres + NUL
    char password[65];   // hasta 64 caracteres + NUL
    bool use_static_ip;
    char static_ip[16];  // "192.168.1.50" o vacío
    char gateway[16];
    char netmask[16];
    char speaker_id[32]; // identificador legible de la zona/población, opcional
} nvs_wifi_config_t;

// Lee la config guardada. Devuelve false si no hay ninguna guardada todavía
// (p.ej. primer arranque de fábrica), en cuyo caso `out` queda sin definir.
bool nvs_config_load(nvs_wifi_config_t *out);

esp_err_t nvs_config_save(const nvs_wifi_config_t *cfg);

// Borra toda la configuración guardada (fuerza modo AP de configuración en
// el siguiente arranque).
esp_err_t nvs_config_clear(void);
