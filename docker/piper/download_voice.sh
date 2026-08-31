#!/usr/bin/env bash
# Descarga los modelos de voz es_ES desde rhasspy/piper-voices en
# HuggingFace. Se ejecuta una vez; el resultado no se versiona en git, se
# monta como volumen en el sidecar de Piper.
#
# - davefx (medium): voz original del proyecto, se mantiene como fallback.
# - sharvard (medium): modelo multi-speaker (locutor 0 = masculina, 1 =
#   femenina) con el mismo acento de España -- es lo que permite elegir
#   género de voz desde /settings sin arriesgarse a un acento distinto.
set -euo pipefail

VOICE_DIR="$(dirname "$0")/voices"
mkdir -p "$VOICE_DIR"

BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES"

download() {
    local voice="$1" quality="$2"
    local url="$BASE_URL/$voice/$quality"
    local name="es_ES-${voice}-${quality}"
    curl -L -o "$VOICE_DIR/${name}.onnx" "$url/${name}.onnx"
    curl -L -o "$VOICE_DIR/${name}.onnx.json" "$url/${name}.onnx.json"
}

download davefx medium
download sharvard medium

echo "Modelos descargados en $VOICE_DIR"
