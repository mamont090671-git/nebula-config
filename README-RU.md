# Генератор конфигураций Nebula VPN

Генератор конфигураций для сети [Nebula VPN](https://github.com/slackhq/nebula) на Python. Автоматически создаёт конфигурации узлов и сертификаты на основе единого мастер-файла.

## Возможности

- **Автоматическая генерация конфигураций** из `config-nebula.yaml`
- **Генерация сертификатов** для CA и всех узлов (формат V2)
- **Статические карты хостов** с поддержкой IPv4 и IPv6
- **Скрипты развертывания** для удобного развертывания на целевые серверы
- **Поддержка резервных копий** существующих конфигураций

## Требования

- Python 3.8+
- Бинарники Nebula v2 (`nebula-cert` из https://github.com/slackhq/nebula/releases)
- Для IPv6: сборка Nebula должна поддерживать IPv6

## Структура проекта

```
nebula-config/
├── config-nebula.yaml          # Мастер-файл конфигурации сети
├── generate_configs.py         # Основной генератор конфигураций
├── generate_deploy.sh          # Скрипт для создания скриптов развертывания
├── for-all/
│   ├── nebula                  # Бинарник nebula
│   ├── nebula-cert             # Бинарник для генерации сертификатов
│   └── nebula_service.sh       # Скрипт для systemd сервиса
├── host/
│   └── config.yaml             # Шаблон конфигурации узла
├── lighthouse/
│   └── config.yaml             # Шаблон конфигурации маяка
├── output/                     # Сгенерированные конфигурации
│   ├── ca/                     # CA сертификаты
│   ├── node-name/              # Конфигурации узлов
│   └── lighthouse-name/        # Конфигурации маяков
├── host/
├── lighthouse/
└── README.md
```

## Формат конфигурации

Создайте файл `config-nebula.yaml` со следующей структурой:

```yaml
net-name: my-network
lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.10/24
      ipv6: fd00:1234:5678:a::10/64
    port: '4242'
    public_ip: 1.2.3.4
    type: LH
  light-2:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.11/24
      ipv6: fd00:1234:5678:a::11/64
    port: '4242'
    public_ip: 5.6.7.8
    type: LH
hosts:
  server-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    public_ip: 9.10.11.12
    type: HOST
  laptop-1:
    groups: home,ssh,admins
    name: laptop-1
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    type: HOST
```

### Описание полей конфигурации

| Поле | Описание |
|------|----------|
| `net-name` | Имя сети, используемое в CA сертификате |
| `lighthouse` | Конфигурации маяков сети |
| `hosts` | Конфигурации обычных узлов |
| `groups` | Комма-разделённый список групп доступа |
| `nebula_ip.ipv4` | Внутренний IPv4 адрес с подсетью |
| `nebula_ip.ipv6` | Внутренний IPv6 адрес с подсетью |
| `port` | Порт для маяков (0 для клиентов) |
| `public_ip` | Публичный IP для пробива NAT (только для маяков) |
| `type` | `LH` для маяка, `HOST` для узла |
| `name` | Имя сертификата (по умолчанию берётся имя узла) |

## Использование

### Генерация всех конфигураций

```bash
cd /путь/к/nebula-config
python3 generate_configs.py
```

Это выполнит:
1. Создаст директорию `output/ca/` и сгенерирует CA если нет
2. Сгенерирует конфигурации для всех узлов и маяков
3. Создаст файлы `*.crt` и `*.key` для каждого узла
4. Скопирует `ca.crt` в каждую директорию узла

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
│   └── nebula_service.sh   # Скрипт systemd сервиса
└── light-1/
    ├── ca.crt
    ├── config.yaml
    ├── light-1.crt
    ├── light-1.key
    ├── nebula
    ├── nebula-cert
    └── nebula_service.sh
```

## Развертывание

### Развертывание на целевой сервер

```bash
cd output/server-1
./deploy.sh
```

Скопирует все необходимые файлы в `/home/mamont/test-n/`.

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

## Генерация сертификатов

### CA сертификат

```bash
./for-all/nebula-cert ca -name "my-network" -version 2 -out-key ca.key -out-crt ca.crt
```

### Сертификат узла

```bash
./for-all/nebula-cert sign \
  -name "server-1" \
  -ip "192.168.10.100/24,fd00:1234:5678:a::100/64" \
  -groups "home,ssh" \
  -ca-crt ca.crt \
  -ca-key ca.key \
  -out-crt server-1.crt \
  -out-key server-1.key
```

## Решение проблем

### Ошибка "CA not found"

```bash
python3 generate_configs.py --generate-ca
```

### Ошибка "nebula-cert not found"

```bash
python3 generate_configs.py --cert-path /путь/к/nebula-cert
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
