#!/usr/bin/env sh
# Siembra /voices (volumen del host, vacío en el primer despliegue) con el
# modelo horneado en la imagen. Si el host ya tiene ficheros ahí (porque el
# usuario actualizó el modelo desde fuera), no se tocan.
set -eu

if [ -z "$(ls -A /voices 2>/dev/null)" ]; then
    echo "entrypoint: /voices vacío, copiando modelo por defecto de la imagen..."
    cp -n /opt/voices-default/* /voices/
fi

exec "$@"
