#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: нужен root" >&2
    exit 1
fi

cat > /etc/systemd/system/nebula.service <<'EOF'
[Unit]
Description=Nebula VPN
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/etc/nebula/nebula -config /etc/nebula/config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nebula.service
systemctl restart nebula.service
echo "Сервис nebula запущен"
