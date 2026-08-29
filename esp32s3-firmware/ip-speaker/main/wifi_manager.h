#pragma once

#include "esp_err.h"
#include <stdbool.h>

// Arranca el stack WiFi en modo STA, conecta con las credenciales de
// wifi_credentials.h y bloquea hasta obtener IP o agotar el timeout.
// Desactiva el ahorro de energía WiFi (WIFI_PS_NONE) tras conectar.
// Se reconecta automáticamente en caso de desconexión.
esp_err_t wifi_manager_start_and_wait(uint32_t timeout_ms);

bool wifi_manager_is_connected(void);

// Devuelve la IP actual como string ("0.0.0.0" si no hay conexión). buf debe tener al menos 16 bytes.
void wifi_manager_get_ip_str(char *buf, size_t buf_len);

// RSSI en dBm del punto de acceso actual. Devuelve ESP_FAIL si no hay conexión.
esp_err_t wifi_manager_get_rssi(int8_t *rssi_dbm);
