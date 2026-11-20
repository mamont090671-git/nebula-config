#!/usr/bin/env bash
# Nebula VPN deploy script
# Запуск: sudo bash nebula_service.sh <path_to_output_dir>
set -euo pipefail

NODE_DIR="${1:?Usage: $0 <path_to_output_dir>}"

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
if ! command -v nebula &>/dev/null; then
    echo "Проверка бинарника nebula..."
    if command -v nebula &>/dev/null; then
        echo "✓ nebula уже установлен: $(which nebula)"
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
            tar -xzf /tmp/nebula.tar.gz -C /tmp/
            cp -f /tmp/nebula/nebula /usr/local/bin/nebula
            chmod +x /usr/local/bin/nebula
            rm -f /tmp/nebula.tar.gz /tmp/nebula
            echo "✓ nebula установлен"
        else
            cp -f "$NEBULA_BIN" /usr/local/bin/nebula
            chmod +x /usr/local/bin/nebula
            echo "✓ nebula скопирован в /usr/local/bin/nebula"
        fi
    fi
else
    echo "✓ nebula уже установлен"
fi

# 4. Настраиваем sysctl
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf
echo "net.ipv6.conf.all.forwarding = 1" >> /etc/sysctl.conf
sysctl -p 2>/dev/null || true
echo "✓ IP forwarding настроен"

# 5. Настраиваем firewall (iptables для nebula)
iptables -N nebula 2>/dev/null || true
iptables -I INPUT -j nebula 2>/dev/null || true
iptables -I FORWARD -j nebula 2>/dev/null || true
iptables -I OUTPUT -j nebula 2>/dev/null || true
echo "✓ Firewall rules добавлены"

# 6. Создаём systemd service
cat > /etc/systemd/system/nebula.service << 'SERVICE'
[Unit]
Description=Nebula VPN
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/nebula -config /etc/nebula/config.yaml
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

# 7. Включаем и запускаем
systemctl daemon-reload
systemctl enable nebula.service
systemctl restart nebula.service

echo "=== Deploy completed ==="
echo "Статус: $(systemctl status nebula --no-pager 2>&1 | head -5)"
echo "Интерфейс: $(ip link show nebula1 2>/dev/null || echo 'не создан')"
