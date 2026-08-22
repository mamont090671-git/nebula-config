# Генератор конфигураций Nebula VPN

Генератор конфигураций для сети [Nebula VPN](https://github.com/slackhq/nebula) на Python. Автоматически создаёт конфигурации узлов, сертификаты и проверяет их корректность на основе единого мастер-файла.

## Возможности

- **Автоматическая генерация конфигураций** из `config-nebula.yaml`
- **Генерация сертификатов** для CA и всех узлов (формат V2)
- **Статические карты хостов** с поддержкой IPv4 и IPv6
- **Верификация сгенерированных конфигов** — автоматическая проверка relay, use_relays, static_host_map, IPv6 hosts
- **Relay-поддержка** — автоматическая генерация relays для NAT-хостов
- **Параметризованные скрипты развертывания** — deploy.sh принимает путь как аргумент
- **Inline CA** — поддержка CA PEM прямо в конфиге
- **Key-based signing** — поддержка `-in-pub` для подписи сертификатов
- **Резервные копии** — автоматический бэкап существующих конфигов

## Требования

- Python 3.8+
- Бинарники Nebula v2 — загружаются скриптом: `bash setup-binaries.sh`
- Для IPv6: сборка Nebula должна поддерживать IPv6

## Структура проекта

```
nebula-config/
├── config-nebula.yaml          # Мастер-файл конфигурации сети
├── generate_configs.py         # Основной генератор конфигураций
├── generate_deploy.sh          # Скрипт для создания deploy.sh
├── setup-binaries.sh           # Скрипт загрузки бинарников Nebula
├── example-config.yml          # Пример мастер-конфига
├── todo-later.md               # Задачи на будущее
├── plan-fixes.md               # План выполненных исправлений
├── for-all/
│   └── nebula_service.sh       # Скрипт для systemd сервиса
├── templates/
│   └── config.yaml             # Единый шаблон конфигурации
└── README.md
```

> **Примечание:** `output/`, `__pycache__/` и бинарники игнорируются git.
> Перед использованием выполните `bash setup-binaries.sh`.

## Формат конфигурации

Создайте файл `config-nebula.yaml` со следующей структурой:

```yaml
net-name: my-network

# Relay-серверы — nebula-IP узлов, через которые клиенты за NAT проходят
relay_servers:
  - 192.168.10.101

# Inline CA PEM (base64, необязательно)
ca_pem: ""

# Key-based signing public address (необязательно)
in_pub: ""

lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.10/24
      ipv6: fd00:1234:5678:a::10/64
    port: '4242'
    public_ip: 1.2.3.4
    am_relay: true        # true для relay-лайтхауса
    type: LH

hosts:
  server-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    public_ip: 9.10.11.12
    port: '4242'           # 4242 = публичный IP, 0 = за NAT
    type: HOST
  laptop-1:
    groups: home,ssh,admins
    name: laptop-1
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: '0'              # 0 = за NAT, будет использовать relay
    type: HOST
```

### Описание полей конфигурации

| Поле | Описание |
|------|----------|
| `net-name` | Имя сети, используемое в CA сертификате |
| `relay_servers` | Список nebula-IP relay-серверов для NAT-хостов |
| `ca_pem` | Inline CA PEM (если пустой — используется путь /etc/nebula/ca.crt) |
| `in_pub` | Публичный адрес для `-in-pub` (key-based signing) |
| `lighthouse` | Конфигурации маяков сети |
| `hosts` | Конфигурации обычных узлов |
| `groups` | Комма-разделённый список групп доступа |
| `nebula_ip.ipv4` | Внутренний IPv4 адрес с подсетью |
| `nebula_ip.ipv6` | Внутренний IPv6 адрес с подсетью |
| `port` | Порт: `4242` для публичных IP, `0` для NAT |
| `public_ip` | Публичный IP (для публичных узлов/маяков) |
| `am_relay` | `true` для relay-лайтхауса |
| `name` | Имя сертификата (по умолчанию берётся имя узла) |

### Relay-архитектура

Для хостов за NAT (port 0) relay обязателен:

**На relay-лайтхаусе:**
```yaml
relay:
  am_relay: true
  use_relays: false
```

**На NAT-клиенте (автоматически):**
```yaml
relays:
  - 192.168.10.101
relay:
  use_relays: true
```

## Использование

### Генерация всех конфигураций

```bash
cd /путь/к/nebula-config
python3 generate_configs.py
```

Выполнит:
1. Проверит/создаст CA
2. Сгенерирует конфигурации для всех узлов и маяков
3. Создаст файлы `*.crt` и `*.key` для каждого узла
4. Скопирует `ca.crt` в каждую директорию узла
5. **Запустит верификацию** — проверит relay, use_relays, static_host_map, IPv6 hosts

### Генерация только CA-сертификата

```bash
python3 generate_configs.py --generate-ca
```

### Генерация сертификатов для конкретных узлов

```bash
python3 generate_configs.py --host server-1 laptop-1
python3 generate_configs.py --light light-1
python3 generate_configs.py --only-hosts --host server-1
python3 generate_configs.py --only-lights --light light-1
```

### Генерация всех сертификатов без конфигов

```bash
python3 generate_configs.py --generate-host-certs
```

### Использование кастомного пути к nebula-cert

```bash
python3 generate_configs.py --cert-path /путь/к/nebula-cert
```

### Генерация скриптов развертывания

```bash
bash generate_deploy.sh
```

Создаст `deploy.sh` в каждой папке узла/маяка в `output/`.

### Использование deploy.sh

```bash
cd output/server-1
./deploy.sh                    # в /etc/nebula/ (по умолчанию)
./deploy.sh /custom/path/      # в указанный путь
```

## Структура выходной директории

После генерации `output/` будет содержать:

```
output/
├── ca/
│   ├── ca.crt              # CA сертификат
│   └── ca.key              # Приватный ключ CA
├── server-1/
│   ├── ca.crt              # CA сертификат (для проверки)
│   ├── config.yaml         # Конфигурация узла
│   ├── server-1.crt        # Сертификат узла
│   ├── server-1.key        # Приватный ключ узла
│   ├── nebula              # Бинарник nebula
│   ├── nebula-cert         # Бинарник nebula-cert
│   ├── nebula_service.sh   # Скрипт systemd сервиса
│   └── deploy.sh           # Скрипт развертывания
└── light-1/
    ├── ca.crt
    ├── config.yaml
    ├── light-1.crt
    ├── light-1.key
    ├── nebula
    ├── nebula-cert
    ├── nebula_service.sh
    └── deploy.sh
```

## Развертывание

### Развертывание на целевой сервер

```bash
cd output/server-1
./deploy.sh          # скопирует в /etc/nebula/
```

### Ручное развертывание

1. Скопируйте файлы из `output/server-1/` на целевой сервер
2. Разместите файлы в `/etc/nebula/`:
   ```bash
   sudo cp -r /путь/к/output/server-1/* /etc/nebula/
   sudo chmod +x /etc/nebula/nebula /etc/nebula/nebula-cert
   ```
3. Создайте systemd сервис:
   ```bash
   sudo cp /etc/nebula/nebula_service.sh /etc/systemd/system/nebula.service
   sudo systemctl daemon-reload
   sudo systemctl enable nebula
   sudo systemctl start nebula
   ```

## Верификация

После каждой генерации автоматически запускается проверка:

- relay_servers не пуст (если есть NAT-хосты с port 0)
- port 0 хосты имеют `use_relays: true` и секцию `relay:`
- relay-лайтхаус имеет `am_relay: true` и `use_relays: false`
- static_host_map заполнен для всех клиентов
- IPv6 hosts секция содержит все лайтхаусы

## Решение проблем

### Ошибка "CA not found"

```bash
python3 generate_configs.py --generate-ca
```

### Ошибка "nebula-cert not found"

```bash
bash setup-binaries.sh
# или: python3 generate_configs.py --cert-path /путь/к/nebula-cert
```

### Пересоздать всё

```bash
rm -rf output/*
python3 generate_configs.py
```

## Рекомендации по безопасности

- Храните `ca.key` в безопасности и оффлайн
- Распространяйте `ca.crt` только для добавления новых узлов
- Сертификаты и ключи узлов можно безопасно распространять их владельцам
- Используйте отдельные группы для разных уровней доступа
- Регулярно обновляйте сертификаты

## Лицензия

Этот проект предоставляется "как есть" для управления конфигурациями Nebula VPN.

## Вклад

Проблемы и pull requests приветствуются. Пожалуйста, убедитесь что ваши изменения сохраняют совместимость с существующим функционалом.
