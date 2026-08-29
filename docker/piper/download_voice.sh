#!/usr/bin/env bash
# Descarga el modelo de voz es_ES-davefx-medium desde rhasspy/piper-voices
# en HuggingFace. Se ejecuta una vez; el resultado (~60MB) no se versiona
# en git, se monta como volumen en el sidecar de Piper.
set -euo pipefail

VOICE_DIR="$(dirname "$0")/voices"
mkdir -p "$VOICE_DIR"

BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium"

curl -L -o "$VOICE_DIR/es_ES-davefx-medium.onnx" "$BASE_URL/es_ES-davefx-medium.onnx"
curl -L -o "$VOICE_DIR/es_ES-davefx-medium.onnx.json" "$BASE_URL/es_ES-davefx-medium.onnx.json"

echo "Modelo descargado en $VOICE_DIR"
