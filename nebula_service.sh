#!/usr/bin/env bash
# Nebula VPN deploy script
# Распаковывается в /tmp/nebula-deploy/<node>/
# Запуск: sudo bash nebula_service.sh <path_to_cert_and_config>
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
if ! command -v nebula &>/dev/null || ! dpkg -l | grep -q "^ii.*nebula"; then
    echo "Проверка бинарника nebula..."
    if command -v nebula &>/dev/null; then
        echo "✓ nebula уже установлен: $(which nebula)"
    else
        # Определяем архитектуру
        ARCH=$(dpkg --print-architecture)
        case "$ARCH" in
            amd64)  NEBULA_ARCH="linux-amd64" ;;
            arm64)  NEBULA_ARCH="linux-arm64" ;;
            armhf)  NEBULA_ARCH="linux-arm" ;;
            *)
                echo "❌ Неизвестная архитектура: $ARCH"
                echo "Ручная установка: https://github.com/slackhq/nebula/releases"
                exit 1
                ;;
        esac

        # Ищем бинарник в текущей директории
        NEBULA_BIN=""
        for candidate in nebula "$NODE_DIR/nebula" "$(pwd)/nebula"; do
            if [ -f "$candidate" ] && file "$candidate" | grep -q "ELF"; then
                NEBULA_BIN="$candidate"
                echo "✓ Найден бинарник: $candidate"
                break
            fi
        done

        # Скачиваем если не нашли
        if [ -z "$NEBULA_BIN" ]; then
            NEBULA_LATEST="https://github.com/slackhq/nebula/releases/latest/download/nebula-amd64.deb"
            echo "Скачивание nebula с GitHub..."
            curl -fsSL "$NEBULA_LATEST" -o /tmp/nebula.deb
            apt-get install -y /tmp/nebula.deb
            rm -f /tmp/nebula.deb
            echo "✓ nebula установлен из .deb"
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
