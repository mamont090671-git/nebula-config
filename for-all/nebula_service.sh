#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: нужен root" >&2
    exit 1
fi

# Создаём пользователя nebula (если нет)
if ! id -u nebula > /dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin nebula 2>/dev/null || true
fi

cat > /etc/systemd/system/nebula.service <<'EOF'
[Unit]
Description=Nebula VPN
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=nebula
Group=nebula
ExecStart=/etc/nebula/nebula -config /etc/nebula/config.yaml
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE
ProtectSystem=strict
ReadWritePaths=/etc/nebula
NoNewPrivileges=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Разрешаем nebula писать в /etc/nebula
chown -R nebula:nebula /etc/nebula 2>/dev/null || true
chmod -R 755 /etc/nebula 2>/dev/null || true

systemctl daemon-reload
systemctl enable nebula.service
systemctl restart nebula.service
echo "Сервис nebula запущен (харденин: непривилегированный юзер, AmbientCapabilities, ProtectSystem)"
