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

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
# GitHub uses 'linux', not 'Linux'
NEBULA_OS="linux"

NEBULA_ARCHIVE="nebula-${NEBULA_OS}-${NEBULA_ARCH}.tar.gz"
DOWNLOAD_URL="https://github.com/slackhq/nebula/releases/latest/download/${NEBULA_ARCHIVE}"

echo "Загрузка Nebula для ${NEBULA_OS}/${NEBULA_ARCH}..."
echo "  Архив: ${NEBULA_ARCHIVE}"
echo "  URL: ${DOWNLOAD_URL}"

# Скачиваем и распаковываем
TMPDIR=$(mktemp -d)
curl -fsSL -o "$TMPDIR/$NEBULA_ARCHIVE" "$DOWNLOAD_URL"

# Распаковываем в for-all/
cd "$TMPDIR"
tar xzf "$TMPDIR/$NEBULA_ARCHIVE"

# Копируем бинарники
cp -f nebula nebula-cert "$TARGET_DIR/"
chmod +x "$TARGET_DIR/nebula" "$TARGET_DIR/nebula-cert"

rm -rf "$TMPDIR"

echo ""
echo "Бинарники в: $TARGET_DIR/"
echo "  nebula:     $(file "$TARGET_DIR/nebula")"
echo "  nebula-cert: $(file "$TARGET_DIR/nebula-cert")"
