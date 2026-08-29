#pragma once

#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>

// Arranca SNTP contra pool.ntp.org y bloquea hasta sincronizar o agotar el
// timeout. Requiere que el WiFi ya esté conectado. Configura la zona horaria
// a Europe/Madrid (con DST) para que los timestamps salgan en hora local.
esp_err_t time_sync_start_and_wait(uint32_t timeout_ms);

bool time_sync_is_synced(void);

// Formatea la hora actual como "DD/MM/YYYY - HH:MM:ss" en buf (>= 24 bytes).
// Si aún no hay sincronización, escribe "null" en buf sin comillas.
void time_sync_format_now(char *buf, size_t buf_len);

// Formatea, en el mismo formato que time_sync_format_now(), el instante de
// hora de pared que corresponde a "hace ago_ms milisegundos" (medidos con el
// reloj monótono de esp_timer_get_time()). Útil para reconstruir la hora de
// pared de un evento del que solo se guardó un timestamp de uptime relativo.
// Si aún no hay sincronización, escribe "null" en buf sin comillas.
void time_sync_format_ago_ms(int64_t ago_ms, char *buf, size_t buf_len);
