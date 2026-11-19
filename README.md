# Nebula VPN Config Generator

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
- **Харденинг systemd** — небло privileges, `ProtectSystem=strict`
- **CI/CD** — ruff + pytest на каждый пуш

## Требования

- Python 3.8+
- Бинарники Nebula v2: `bash setup-binaries.sh`
- Для деплоя: `sshpass` или настроенные SSH-ключи

## Пример конфигурации (config-nebula.yaml)

```yaml
net-name: x-net

# Relay-серверы для NAT-хостов
relay_servers:
  - 192.168.10.101

ca_pem: ""
in_pub: ""
ca_key_path: ""

lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: '4242'
    public_ip: 138.100.15.25
    am_relay: true

hosts:
  # Публичный хост (прямо по hole-punch)
  server-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    port: '4242'
    public_ip: 31.57.105.170
    # ssh_target: user@31.57.105.170:/etc/nebula

  # NAT-хост (port 0 — нужен relay)
  client-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.102/24
      ipv6: fd00:1234:5678:a::102/64
    port: '0'
    # public_ip не нужен — port 0
```

## Структура проекта

```
nebula-config/
├── generate_configs.py         # Основной генератор (+ --push)
├── validators.py         # Валидация конфига
├── nebula_inventory.py         # Динамический инвентарь Ansible
├── setup-binaries.sh           # Загрузка бинарников Nebula
├── templates/
│   └── config.yaml             # Единый шаблон конфига
├── for-all/
│   └── nebula_service.sh       # systemd-сервис (харденён)
├── tests/
│   └── test_config.py          # 23 pytest-теста
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
├── output/                     # Сгенерированные конфиги (gitignore)
└── config-nebula.yaml          # Мастер-конфиг (gitignore)
```

> `output/`, `__pycache__/`, `config-nebula.yaml`, `*.key`, `*.pem`, `for-all/nebula`, `for-all/nebula-cert` — в `.gitignore`.
> Перед использованием: `bash setup-binaries.sh`

## Формат конфигурации

См. `config-nebula.yaml` (не в репозитории) — содержит `net-name`, `relay_servers`, секции `lighthouse` и `hosts` с полями:

| Поле | Описание |
|------|----------|
| `net-name` | Имя сети для CA |
| `relay_servers` | IP relay-серверов |
| `ca_pem` | Inline CA PEM (необязательно) |
| `in_pub` | Key-based signing (необязательно) |
| `ca_key_path` | Путь к внешнему CA-ключу (необязательно) |
| `groups` | Группы доступа (через запятую) |
| `nebula_ip` | Внутренний IP + CIDR (ipv4/ipv6) |
| `port` | `4242` = публичный, `0` = NAT |
| `public_ip` | Публичный IP (для публичных узлов) |
| `am_relay` | Relay-лайтхаус (только для lighthouse) |
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

### Точечная генерация

```bash
python3 generate_configs.py --host server-1
python3 generate_configs.py --only-hosts --host A B
python3 generate_configs.py --light light-1
```

### Деплой на удалённые сервера

```bash
python3 generate_configs.py --push
```

Копирует все файлы из `output/<node>/` на `ssh_target` + `systemctl restart nebula`.

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

6 классов тестов, 23 теста:
- `TestNebulaIPValidation` (5): IPv4/IPv6 CIDR
- `TestHostConfigValidation` (6): порт, public_ip, nebula_ip
- `TestLighthouseConfigValidation` (2): am_relay без public_ip
- `TestNebulaConfigValidation` (4): валидный конфиг, пустой net-name, дубликаты relay
- `TestValidateConfigSafe` (3): safe валидация
- `TestRealConfigValidation` (2): реальный конфиг, relay для NAT

### Генерация CA

```bash
python3 generate_configs.py --generate-ca
python3 generate_configs.py --generate-host-certs
```

## Структура output/

```
output/
├── ca/
│   ├── ca.crt
│   └── ca.key
├── <node-name>/
│   ├── config.yaml
│   ├── <cert-name>.crt
│   ├── <cert-name>.key
│   └── ca.crt
```

## Развертывание

### Через --push (автоматически)

```bash
python3 generate_configs.py --push
```

### Ручное

```bash
cd output/<node-name>
scp -r * user@remote-host:/etc/nebula/
ssh user@remote-host "systemctl restart nebula"
```

### systemd-сервис (харденён)

```bash
sudo cp for-all/nebula_service.sh /etc/systemd/system/nebula.service
sudo systemctl daemon-reload
sudo systemctl enable nebula
sudo systemctl start nebula
```

Сервис запущен от пользователя `nebula` с ограниченным набором capabilities:
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `ProtectSystem=strict`, `ProtectHome=true`, `NoNewPrivileges=true`
- `ReadWritePaths=/etc/nebula`

## Верификация

Автоматическая проверка после генерации:
- relay_servers не пуст (при NAT-хостах)
- port 0 хосты имеют `use_relays: true`
- relay-лайтхаус имеет `am_relay: true`
- static_host_map заполнен
- IPv6 hosts секция содержит все лайтхаусы

## Безопасность

- `ca_key_path` — внешний CA-ключ (не генерируется в `output/ca/`)
- systemd-харденинг — `ProtectSystem=strict`, `NoNewPrivileges=true`
- Храните `ca.key` оффлайн
- Регулярно обновляйте сертификаты

## CI/CD

GitHub Actions: `ruff check` + `ruff format --check` + `pytest` на каждый push/PR в master/main.

## Лицензия

Этот проект предоставляется "как есть" для управления конфигурациями Nebula VPN.
