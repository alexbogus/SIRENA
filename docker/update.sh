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

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [update.sh] $*"; }

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
