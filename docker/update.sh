#!/usr/bin/env bash
# Actualiza SIRENA en el VPS: git pull + build + up -d, con rollback automático
# si el health check falla. Pensado para lanzarse a mano o por cron.
set -euo pipefail

BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
LOCK_FILE="/tmp/sirena-update.lock"
HEALTH_RETRIES=15
HEALTH_INTERVAL=2

DB_PATH="$SCRIPT_DIR/data/dashboard.db"
BACKUP_DIR="$SCRIPT_DIR/backups"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [update.sh] $*"; }

# --- Backup de la base de datos: se ejecuta al principio de CADA arranque
# del script (haya o no versión nueva que desplegar), para que cualquier
# `up -d` deje siempre un punto de restauración reciente -- ver el incidente
# que motivó esto: un cambio de rutas de volúmenes dejó el dashboard con una
# BD vacía sin que el healthcheck (solo hace SELECT 1) lo detectara. ---

ensure_sqlite3() {
    if command -v sqlite3 >/dev/null 2>&1; then
        return 0
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        log "ERROR: sqlite3 no está instalado y no hay apt-get para instalarlo automáticamente. Instálalo a mano."
        return 1
    fi
    log "sqlite3 no está instalado, instalando con apt..."
    local apt_cmd="apt-get"
    if [[ "$(id -u)" -ne 0 ]]; then
        apt_cmd="sudo apt-get"
    fi
    if $apt_cmd update -qq && $apt_cmd install -y -qq sqlite3; then
        log "sqlite3 instalado correctamente."
        return 0
    fi
    log "ERROR: no se pudo instalar sqlite3 automáticamente."
    return 1
}

backup_db() {
    if [[ ! -f "$DB_PATH" ]]; then
        log "No hay base de datos en $DB_PATH todavía (primer arranque); se omite el backup."
        return 0
    fi
    if ! ensure_sqlite3; then
        return 1
    fi
    mkdir -p "$BACKUP_DIR"
    local dest="$BACKUP_DIR/dashboard_$(date '+%Y%m%d_%H%M%S').db"
    if ! sqlite3 "$DB_PATH" ".backup '$dest'"; then
        log "ERROR: falló el backup de la base de datos."
        return 1
    fi
    log "Backup creado: $dest"
    # Retención: se conservan BACKUP_RETENTION_DAYS días de copias (no solo
    # la última), podando el resto en cada ejecución -- mismo criterio que
    # LOG_RETENTION_DAYS/dedupe_retention_days en el dashboard.
    find "$BACKUP_DIR" -maxdepth 1 -name 'dashboard_*.db' -mtime "+$BACKUP_RETENTION_DAYS" -delete
    return 0
}

is_running() {
    local cid
    cid="$(docker compose -f "$COMPOSE_FILE" ps -q dashboard 2>/dev/null || true)"
    [[ -n "$cid" ]] && [[ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" == "true" ]]
}

check_health() {
    local cid status
    cid="$(docker compose -f "$COMPOSE_FILE" ps -q dashboard 2>/dev/null || true)"
    if [[ -z "$cid" ]]; then
        return 1
    fi
    for ((i = 1; i <= HEALTH_RETRIES; i++)); do
        status="$(docker inspect --format='{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "unknown")"
        if [[ "$status" == "healthy" ]]; then
            return 0
        fi
        log "health check: $status (intento $i/$HEALTH_RETRIES)"
        sleep "$HEALTH_INTERVAL"
    done
    return 1
}

deploy() {
    log "Construyendo imágenes..."
    docker compose -f "$COMPOSE_FILE" build
    log "Levantando servicios..."
    docker compose -f "$COMPOSE_FILE" up -d
}

# --- Lock: evita que dos ejecuciones (p.ej. dos disparos de cron) se solapen ---
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "Ya hay una actualización en curso. Saliendo."
    exit 0
fi

cd "$REPO_ROOT"

if ! backup_db; then
    log "ERROR: no se pudo garantizar el backup de la base de datos. Abortando para no desplegar sin red de seguridad."
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    log "ERROR: el árbol de trabajo tiene cambios sin commitear en $REPO_ROOT. Abortando para no pisarlos."
    exit 1
fi

log "Comprobando novedades en origin/$BRANCH..."
git fetch origin "$BRANCH"

LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL_HEAD" == "$REMOTE_HEAD" ]]; then
    log "Sin novedades (HEAD=$LOCAL_HEAD)."
    if is_running; then
        log "El servicio ya está corriendo. Nada que hacer."
        exit 0
    fi
    log "El servicio no está corriendo. Levantándolo con la versión actual..."
    deploy
    if check_health; then
        log "Servicio levantado y sano."
        exit 0
    fi
    log "ERROR: el servicio no pasó el health check. Revisión manual necesaria (no hay versión anterior a la que volver)."
    exit 1
fi

log "Nueva versión disponible: $LOCAL_HEAD -> $REMOTE_HEAD"
git pull --ff-only origin "$BRANCH"

if ! docker compose -f "$COMPOSE_FILE" build; then
    log "ERROR: falló el build de la nueva versión. Revirtiendo el repo a $LOCAL_HEAD (el contenedor en marcha no se ha tocado)."
    git reset --hard "$LOCAL_HEAD"
    exit 1
fi

log "Levantando la nueva versión..."
docker compose -f "$COMPOSE_FILE" up -d

if check_health; then
    log "Actualización correcta. Nueva versión: $(git rev-parse HEAD)"
    log "Limpiando imágenes dangling..."
    docker image prune -f
    exit 0
fi

log "ERROR: la nueva versión no pasó el health check. Haciendo rollback a $LOCAL_HEAD..."
git reset --hard "$LOCAL_HEAD"
docker compose -f "$COMPOSE_FILE" build
docker compose -f "$COMPOSE_FILE" up -d

if check_health; then
    log "Rollback correcto: el servicio vuelve a estar sano en la versión anterior ($LOCAL_HEAD)."
else
    log "CRÍTICO: el rollback también falló el health check. Revisión manual urgente."
fi
exit 1
