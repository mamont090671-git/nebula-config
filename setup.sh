#!/usr/bin/env bash
# Установочный скрипт для nebula-config
# Скачивает nebula binaries и устанавливает Python зависимости
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Установка nebula-config ==="

# 1. Определяем архитектуру
ARCH=$(dpkg --print-architecture 2>/dev/null || uname -m)
case "$ARCH" in
    x86_64|amd64)  NEBULA_ARCH="linux-amd64" ;;
    aarch64|arm64) NEBULA_ARCH="linux-arm64" ;;
    armv7l|armhf)  NEBULA_ARCH="linux-arm-7" ;;
    *)
        echo "❌ Неизвестная архитектура: $ARCH"
        exit 1
        ;;
esac

# 2. Получаем последнюю версию
VERSION=$(curl -fsSL "https://api.github.com/repos/slackhq/nebula/releases/latest" | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
if [ -z "$VERSION" ]; then
    echo "❌ Не удалось получить версию nebula"
    exit 1
fi
echo "✓ Последняя версия: $VERSION"

# 3. Скачиваем и распаковываем
ARCHIVE="nebula-${VERSION}-${NEBULA_ARCH}.tar.gz"
echo "Скачивание $ARCHIVE..."
wget -vO /tmp/$ARCHIVE -L --trust-server-names "https://github.com/slackhq/nebula/releases/download/v${VERSION}/${ARCHIVE}"
tar xzf /tmp/$ARCHIVE -C "$SCRIPT_DIR/"
rm -f /tmp/$ARCHIVE

# Копируем бинарники в корень проекта
cp -f "$SCRIPT_DIR/nebula" "$SCRIPT_DIR/"
cp -f "$SCRIPT_DIR/nebula-cert" "$SCRIPT_DIR/"
chmod +x "$SCRIPT_DIR/nebula" "$SCRIPT_DIR/nebula-cert"

echo "✓ Бинарники: nebula, nebula-cert"

# 4. Устанавливаем Python зависимости
echo "Установка Python зависимостей..."
pip install --user pyyaml validators
echo "✓ pyyaml, validators установлены"

# 5. Создаём output/ca/ если нет
mkdir -p "$SCRIPT_DIR/output/ca"

echo "=== Установка завершена ==="
echo "Запуск: python3 generate_configs.py"
echo "Сгенерировать CA: python3 generate_configs.py --generate-ca"
