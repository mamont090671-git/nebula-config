# Nebula VPN Config Generator

[![CI](https://github.com/mamont090671-git/nebula-config/actions/workflows/ci.yml/badge.svg)](https://github.com/mamont090671-git/nebula-config/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/mamont090671-git/nebula-config)](https://github.com/mamont090671-git/nebula-config/releases/tag/v1.0.0)

Генератор конфигураций для сети [Nebula VPN](https://github.com/slackhq/nebula). Создаёт конфиги, сертификаты и деплоит на сервера из единого master-конфига.

## Возможности

- **Генерация конфигураций** из `config-nebula.yaml`
- **Валидация конфига** — CIDR, порт 0-65535, обязательные поля
- **Автоотсечение CIDR-маски** через `ipaddress` stdlib
- **Аутентификация через SSH** — `--push` деплой на удалённые сервера
- **Динамический инвентарь Ansible** — `nebula_inventory.py`
- **Inline CA** — CA PEM прямо в конфиге
- **Key-based signing** — поддержка `-in-pub`
- **Оффлайн CA** — `ca_key_path` для внешнего ключа
- **Харденинг systemd** — NoNewPrivileges, `ProtectSystem=strict`
- **CI/CD** — ruff + pytest на каждый пуш

## Требования

- Python 3.8+
- Для деплоя: `sshpass` или настроенные SSH-ключи
- SSH-доступ к целевым серверам (указан в `ssh_target`)

## Пример конфигурации (config-nebula.yaml)

```yaml
net-name: my-net

# Relay-серверы для NAT-хостов
relay_servers:
  - 192.168.10.101

ca_pem: ""
in_pub: ""
ca_key_path: ""

lighthouse:
  lh-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: 4242
    public_ip: 203.0.113.1
    am_relay: true
    type: LH

hosts:
  # Публичный хост (прямо по hole-punch)
  server-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    port: 4242
    public_ip: 203.0.113.2
    type: HOST
    # ssh_target: user@host:/etc/nebula

  # NAT-хост (port 0 — нужен relay)
  nat-client:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.102/24
      ipv6: fd00:1234:5678:a::102/64
    port: 0
    type: HOST
    # public_ip не нужен — port 0
```

## Структура проекта

```
nebula-config/
├── setup.sh                  # Установочный скрипт (nebula binaries + pip)
├── generate_configs.py       # Генератор + автодеплой (--push)
├── validators.py             # Валидация конфига
├── nebula_inventory.py       # Динамический инвентарь Ansible
├── nebula_service.sh         # Deploy-скрипт (бинарник + systemd)
├── templates/
│   └── config.yaml           # Единый шаблон конфига
├── tests/
│   └── test_config.py        # 31 pytest-тест
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI
├── output/                   # Сгенерированные конфиги (gitignore)
└── config-nebula.yaml        # Мастер-конфиг (gitignore)
```

> `output/`, `__pycache__/`, `config-nebula.yaml`, `*.key`, `*.pem`, `nebula`, `nebula-cert` — в `.gitignore`.

## Формат конфигурации

См. `config-nebula.yaml` (не в репозитории) — содержит `net-name`, `relay_servers`, секции `lighthouse` и `hosts` с полями:

| Поле | Описание |
|------|----------|
| `net-name` | Имя сети для CA |
| `relay_servers` | Nebula IP relay-серверов |
| `ca_pem` | Inline CA PEM (необязательно) |
| `in_pub` | Key-based signing (необязательно) |
| `ca_key_path` | Путь к внешнему CA-ключу (необязательно) |
| `blocklist` | SHA-256 отпечатки отозванных сертификатов (необязательно) |
| `groups` | Группы доступа (через запятую) |
| `nebula_ip` | Внутренний IP + CIDR (ipv4/ipv6) |
| `port` | `4242` = публичный, `0` = NAT |
| `public_ip` | Публичный IP (для публичных узлов и lighthouse) |
| `am_relay` | Relay-лайтхаус (только для lighthouse) |
| `type` | `LH` или `HOST` |
| `ssh_target` | `user@host:/etc/nebula` для `--push` |

### Relay-архитектура

NAT-хосты (`port: 0`) → `use_relays: true` + `relays:` секция.
Relay-лайтхаус → `am_relay: true` + `use_relays: false`.
Публичные хосты → `use_relays: false`.

## Использование

### Генерация всех конфигураций

```bash
python3 generate_configs.py
```

Проверит/создаст CA → сгенерирует конфиги → создаст сертификаты → верификация.

### Проверка сертификатов

```bash
python3 generate_configs.py --check-certs
```

Проверяет все `.crt` в `output/` через `nebula-cert print`, выводит таблицу с оставшимся сроком действия. Exit 1 если до истечения < 30 дней.

### Точечная генерация

```bash
python3 generate_configs.py --host server-1
python3 generate_configs.py --only-hosts --host A B
python3 generate_configs.py --only-lighthouses --host A B
```

### Деплой на удалённые сервера

```bash
python3 generate_configs.py --push
```

**Автоматически:**
1. Скачивает подходящий бинарник Nebula (определяет архитектуру через SSH)
2. Копирует конфиги + сертификаты на сервер
3. Создаёт systemd-сервис
4. Перезапускает nebula и показывает статус

### Динамический инвентарь Ansible

```bash
ansible-inventory --list -i nebula_inventory.py
ansible-playbook -i nebula_inventory.py deploy.yml --limit Nebula
ansible-playbook -i nebula_inventory.py deploy.yml --limit home
```

### Тесты

```bash
pytest tests/test_config.py -v
```

8 классов тестов, 31 тест:
- `TestNebulaIPValidation` (5): IPv4/IPv6 CIDR
- `TestHostConfigValidation` (7): порт, public_ip, nebula_ip
- `TestLighthouseConfigValidation` (2): am_relay без public_ip
- `TestNebulaConfigValidation` (4): валидный конфиг, пустой net-name, дубликаты relay
- `TestValidateConfigSafe` (3): safe валидация
- `TestRealConfigValidation` (2): реальный конфиг, relay для NAT
- `TestBlocklistValidation` (5): валидация SHA-256 отпечатков
- `TestCheckCertsParsing` (3): парсинг nebula-cert print

### Генерация CA

```bash
python3 generate_configs.py --generate-ca
python3 generate_configs.py --generate-host-certs
```

## Структура output/

Каждая папка `output/<node>/` содержит:

| Файл | Описание |
|------|----------|
| `config.yaml` | Единый Nebula V2 конфиг (pki, firewall, lighthouse, relay, static_host_map, tun) |
| `<имя>.crt` | Сертификат узла |
| `<имя>.key` | Приватный ключ узла |
| `ca.crt` | CA-сертификат |
| `nebula_service.sh` | Deploy-скрипт (бинарник + systemd, всё в `/etc/nebula/`) |

## Развертывание

### Через --push (автоматически)

```bash
python3 generate_configs.py --push
```

### Ручное

```bash
cd output/<node-name>
scp -r * user@remote-host:/etc/nebula/
ssh user@remote-host "sudo bash /etc/nebula/nebula_service.sh /etc/nebula"
```

### systemd-сервис (харденён)

Сервис запущен с ограниченным набором capabilities:
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `ProtectSystem=strict`, `ProtectHome=yes`, `NoNewPrivileges=true`
- `ReadWritePaths=/etc/nebula`

## Безопасность

- `ca_key_path` — внешний CA-ключ (не генерируется в `output/ca/`)
- `blocklist` — отзыв сертификатов по SHA-256 отпечатку
- systemd-харденинг — `ProtectSystem=strict`, `NoNewPrivileges=true`
- Храните `ca.key` оффлайн
- Регулярно обновляйте сертификаты
- Для обновления blocklist без разрыва туннелей: `systemctl reload nebula`

## CI/CD

GitHub Actions: `ruff check` + `ruff format --check` + `pytest` на каждый push/PR в master/main.

## License

MIT License — see [LICENSE](LICENSE) file.
