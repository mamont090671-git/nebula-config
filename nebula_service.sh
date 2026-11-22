#!/usr/bin/env bash
# Nebula VPN deploy script
# Запуск: sudo bash nebula_service.sh <path_to_output_dir>
# Всё nebula: /etc/nebula/
set -euo pipefail

NODE_DIR="${1:?Usage: $0 <path_to_output_dir>}"
NEBULA_HOME="/etc/nebula"

echo "=== Nebula VPN Deploy ==="

# Проверка: если NODE_DIR == /etc/nebula, бэкап не нужен
SAME_PATH=false
if [ "$(realpath "$NODE_DIR" 2>/dev/null)" = "$(realpath "$NEBULA_HOME" 2>/dev/null)" ]; then
    SAME_PATH=true
    echo "⚠ NODE_DIR совпадает с NEBULA_HOME — пропускаем копирование"
fi

# 1. Создаём директорию для nebula
mkdir -p /etc/nebula

# 2. Бэкап текущего конфига ДО любых изменений (только если пути разные)
if [ "$SAME_PATH" = false ] && [ -f /etc/nebula/config.yaml ]; then
    cp -f /etc/nebula/config.yaml /etc/nebula/config.yaml.bak
    echo "✓ Бэкап: config.yaml.bak"
fi

# 3. Копируем конфиг и сертификаты (только если пути разные)
if [ "$SAME_PATH" = false ]; then
    cp -f "$NODE_DIR/config.yaml" /etc/nebula/config.yaml
    [ -f "$NODE_DIR/ca.crt" ] && cp -f "$NODE_DIR/ca.crt" /etc/nebula/ca.crt
    cp -f "$NODE_DIR"/*.crt /etc/nebula/
    cp -f "$NODE_DIR"/*.key /etc/nebula/
    echo "✓ Конфиг и сертификаты скопированы"
else
    echo "⚠ Пропуск копирования (файлы уже в /etc/nebula/)"
fi

# 4. Скачиваем nebula если не установлен
if ! command -v "$NEBULA_HOME/nebula" &>/dev/null; then
    echo "Проверка бинарника nebula..."
    # Определяем архитектуру
    ARCH=$(dpkg --print-architecture 2>/dev/null || uname -m)
    case "$ARCH" in
        x86_64|amd64)  NEBULA_ARCH="linux-amd64" ;;
        aarch64|arm64) NEBULA_ARCH="linux-arm64" ;;
        armv7l|armhf)  NEBULA_ARCH="linux-arm-7" ;;
        *)
            echo "❌ Неизвестная архитектура: $ARCH"
            echo "Ручная установка: https://github.com/slackhq/nebula/releases"
            exit 1
            ;;
    esac

    # Ищем бинарник в текущей директории
    NEBULA_BIN=""
    for candidate in "$NODE_DIR/nebula" nebula; do
        if [ -f "$candidate" ] && file "$candidate" | grep -q "ELF"; then
            NEBULA_BIN="$candidate"
            echo "✓ Найден бинарник: $candidate"
            break
        fi
    done

    # Скачиваем если не нашли — используем GitHub API для надёжности
    if [ -z "$NEBULA_BIN" ]; then
        echo "Скачивание nebula для $ARCH с GitHub..."
        # Получаем URL из GitHub API
        DOWNLOAD_URL=$(curl -fsSL "https://api.github.com/repos/slackhq/nebula/releases/latest" \
            | grep -oP '"browser_download_url":\s*"\K[^"]*linux-'"$ARCH"'.*\.tar\.gz' \
            | head -1)
        if [ -z "$DOWNLOAD_URL" ]; then
            # Fallback на жёсткую ссылку
            DOWNLOAD_URL="https://github.com/slackhq/nebula/releases/latest/download/nebula-${NEBULA_ARCH}.tar.gz"
        fi
        curl -fsSL "$DOWNLOAD_URL" -o /tmp/nebula.tar.gz
        tar -xzf /tmp/nebula.tar.gz -C "$NEBULA_HOME/"
        rm -f /tmp/nebula.tar.gz
        chmod +x "$NEBULA_HOME/nebula"
        echo "✓ nebula установлен в $NEBULA_HOME"
    else
        cp -f "$NEBULA_BIN" "$NEBULA_HOME/nebula"
        chmod +x "$NEBULA_HOME/nebula"
        echo "✓ nebula скопирован в $NEBULA_HOME"
    fi
else
    echo "✓ nebula уже установлен: $NEBULA_HOME/nebula"
fi

# 5. Создаём systemd service (синхронизировано с templates/nebula.service)
cat > /etc/systemd/system/nebula.service << 'SERVICE'
[Unit]
Description=Nebula overlay networking
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
ExecStart=/etc/nebula/nebula -config /etc/nebula/config.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

# Hardening
User=root
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE
ProtectSystem=strict
ProtectHome=true
NoNewPrivileges=true
ReadWritePaths=/etc/nebula
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE

# 6. Тест конфига перед запуском
echo "Тест конфигурации..."
if "$NEBULA_HOME/nebula" -test -config /etc/nebula/config.yaml 2>&1; then
    echo "✓ Конфиг валиден"
else
    echo "❌ Тест конфига FAILED — откат"
    if [ -f /etc/nebula/config.yaml.bak ]; then
        cp -f /etc/nebula/config.yaml.bak /etc/nebula/config.yaml
        echo "✓ Откат: config.yaml.bak → config.yaml"
    fi
    echo "⚠ Откат: nebula НЕ запущен"
    exit 1
fi

# 7. Включаем и запускаем
systemctl daemon-reload
systemctl enable nebula.service
systemctl restart nebula.service

echo "=== Deploy completed ==="
echo "Статус: $(systemctl status nebula --no-pager 2>&1 | head -5)"
echo "Интерфейс: $(ip link show nebula1 2>/dev/null || echo 'не создан')"
