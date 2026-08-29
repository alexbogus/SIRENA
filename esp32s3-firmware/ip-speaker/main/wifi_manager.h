#pragma once

#include "esp_err.h"
#include <stdbool.h>

typedef enum {
    WIFI_MANAGER_STA_CONNECTED, // conectado a la red configurada
    WIFI_MANAGER_AP_CONFIG,     // sin credenciales válidas (o botón mantenido): modo AP de configuración
} wifi_manager_result_t;

// Inicializa NVS + WiFi. Prioridad de credenciales: NVS (guardadas vía el
// portal de configuración) > wifi_credentials.h (valores compilados, solo
// para desarrollo). Si no hay credenciales válidas, si la conexión falla
// tras `timeout_ms`, o si el botón BOOT se mantiene pulsado en el arranque,
// levanta un AP temporal "IPSpeaker-Config-XXXX" (XXXX = sufijo de MAC) y
// devuelve WIFI_MANAGER_AP_CONFIG -- el llamador debe entonces arrancar
// http_config_server_start().
wifi_manager_result_t wifi_manager_start(uint32_t timeout_ms);

bool wifi_manager_is_connected(void);

// Devuelve la IP actual (STA o AP según el modo) como string ("0.0.0.0" si
// no hay ninguna). buf debe tener al menos 16 bytes.
void wifi_manager_get_ip_str(char *buf, size_t buf_len);

// RSSI en dBm del punto de acceso actual. Devuelve ESP_FAIL si no hay conexión STA.
esp_err_t wifi_manager_get_rssi(int8_t *rssi_dbm);
