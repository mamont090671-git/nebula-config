#!/usr/bin/env bash
# Nebula VPN deploy script
# Запуск: sudo bash nebula_service.sh <path_to_output_dir>
# Всё nebula: /etc/nebula/
set -euo pipefail

NODE_DIR="${1:?Usage: $0 <path_to_output_dir>}"
NEBULA_HOME="/etc/nebula"

echo "=== Nebula VPN Deploy ==="

# 1. Создаём директорию для nebula
mkdir -p /etc/nebula

# 2. Копируем конфиг и сертификаты
cp -f "$NODE_DIR/config.yaml" /etc/nebula/config.yaml
cp -f "$NODE_DIR/ca.crt" /etc/nebula/ca.crt
cp -f "$NODE_DIR"/*.crt /etc/nebula/
cp -f "$NODE_DIR"/*.key /etc/nebula/

echo "✓ Конфиг и сертификаты скопированы"

# 3. Скачиваем nebula если не установлен
if ! command -v "$NEBULA_HOME/nebula" &>/dev/null; then
    echo "Проверка бинарника nebula..."
    if command -v "$NEBULA_HOME/nebula" &>/dev/null; then
        echo "✓ nebula уже установлен: $NEBULA_HOME/nebula"
    else
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

        # Скачиваем если не нашли
        if [ -z "$NEBULA_BIN" ]; then
            echo "Скачивание nebula для $ARCH с GitHub..."
            curl -fsSL "https://github.com/slackhq/nebula/releases/latest/download/nebula-${NEBULA_ARCH}.tar.gz" -o /tmp/nebula.tar.gz
            tar -xzf /tmp/nebula.tar.gz -C "$NEBULA_HOME/"
            rm -f /tmp/nebula.tar.gz
            chmod +x "$NEBULA_HOME/nebula"
            echo "✓ nebula установлен в $NEBULA_HOME"
        else
            cp -f "$NEBULA_BIN" "$NEBULA_HOME/nebula"
            chmod +x "$NEBULA_HOME/nebula"
            echo "✓ nebula скопирован в $NEBULA_HOME"
        fi
    fi
else
    echo "✓ nebula уже установлен: $NEBULA_HOME/nebula"
fi

# 4. Создаём systemd service
cat > /etc/systemd/system/nebula.service << 'SERVICE'
[Unit]
Description=Nebula VPN
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/etc/nebula/nebula -config /etc/nebula/config.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/etc/nebula
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
SERVICE

# 5. Бэкап текущего конфига
if [ -f /etc/nebula/config.yaml ]; then
    cp -f /etc/nebula/config.yaml /etc/nebula/config.yaml.bak
    echo "✓ Бэкап: config.yaml.bak"
fi

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
