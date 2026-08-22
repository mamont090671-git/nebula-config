#!/usr/bin/env bash
# Загрузка бинарников Nebula из официального репозитория
# Использование: ./setup-binaries.sh [--dir path]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${2:-"$SCRIPT_DIR/for-all"}"
mkdir -p "$TARGET_DIR"

# Определяем архитектуру
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)   NEBULA_ARCH="amd64" ;;
    aarch64)  NEBULA_ARCH="arm64" ;;
    arm64)    NEBULA_ARCH="arm64" ;;
    *)
        echo "Ошибка: архитектура $ARCH не поддерживается (ожидается x86_64 или aarch64)"
        exit 1
        ;;
esac

# Определяем ОС
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

# Загружаем последнюю версию
echo "Загрузка Nebula для $OS/$ARCH..."

NEBULA_URL="https://github.com/slackhq/nebula/releases/latest/download/nebula-$OS-$ARCH"
NEBULA_CERT_URL="https://github.com/slackhq/nebula/releases/latest/download/nebula-cert-$OS-$ARCH"

# nebula
if [ ! -f "$TARGET_DIR/nebula" ] || ! "$TARGET_DIR/nebula" --version > /dev/null 2>&1; then
    echo "  [1/2] nebula..."
    curl -fsSL -o "$TARGET_DIR/nebula.tmp" "$NEBULA_URL"
    chmod +x "$TARGET_DIR/nebula.tmp"
    mv "$TARGET_DIR/nebula.tmp" "$TARGET_DIR/nebula"
    echo "  ✓ nebula установлен"
else
    echo "  ✓ nebula уже есть"
fi

# nebula-cert
if [ ! -f "$TARGET_DIR/nebula-cert" ] || ! "$TARGET_DIR/nebula-cert" version > /dev/null 2>&1; then
    echo "  [2/2] nebula-cert..."
    curl -fsSL -o "$TARGET_DIR/nebula-cert.tmp" "$NEBULA_CERT_URL"
    chmod +x "$TARGET_DIR/nebula-cert.tmp"
    mv "$TARGET_DIR/nebula-cert.tmp" "$TARGET_DIR/nebula-cert"
    echo "  ✓ nebula-cert установлен"
else
    echo "  ✓ nebula-cert уже есть"
fi

echo ""
echo "Бинарники в: $TARGET_DIR/"
