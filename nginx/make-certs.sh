#!/usr/bin/env bash
# Self-signed certificate for local use.
# CN and SAN come from DOMAIN in the environment or ../../.env.
# Replace the files with a real certificate before production.
set -euo pipefail

cd "$(dirname "$0")/certs"

if [[ -f ../../.env ]]; then
    set -a; source ../../.env; set +a
fi
DOMAIN="${DOMAIN:-localhost}"

CRT="mirror.crt"
KEY="mirror.key"

if [[ -f "$CRT" && -f "$KEY" ]]; then
    echo "Сертифікат уже є: nginx/certs/$CRT"
    echo "Видали його, якщо треба перегенерувати."
    exit 0
fi

echo "Генерую self-signed сертифікат для $DOMAIN..."

openssl req -x509 -nodes -newkey rsa:2048 \
    -days 825 \
    -keyout "$KEY" \
    -out "$CRT" \
    -subj "/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"

chmod 644 "$CRT"
chmod 600 "$KEY"

echo
echo "Готово:"
echo "  nginx/certs/$CRT"
echo "  nginx/certs/$KEY"
echo
echo "This certificate is self-signed. The browser will warn until you trust it."
echo "For production, replace these files with a certificate for $DOMAIN."
