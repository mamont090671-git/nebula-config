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

## Установка

```bash
./setup.sh
```

Скачивает бинарники Nebula, устанавливает Python-зависимости, создаёт `output/ca/`.

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
python3 generate_configs.py --only-lights --light A B
```

### Деплой на удалённые сервера

```bash
python3 generate_configs.py --push
```

**Предпросмотр перед деплоем:**

```bash
python3 generate_configs.py --push --dry-run
```

Покажет какие узлы и файлы изменятся, без фактического деплоя.

**Автоматически:**
1. Скачивает подходящий бинарник Nebula (определяет архитектуру через SSH)
2. Копирует конфиги + сертификаты на сервер
3. Создаёт systemd-сервис
4. Перезапускает nebula и показывает статус

**Безопасность деплоя:**
- Перед заменой конфига — **бэкап** `config.yaml.bak`
- **`nebula -test`** валидация перед запуском
- Если тест не прошёл — **авто-откат** из бэкапа, nebula **не стартует**
- Сервер не потеряет связь при ошибке в конфиге

**Для автодеплоя** в `config-nebula.yaml` укажи `ssh_target` для каждого узла:

```yaml
hosts:
  server-1:
    # ... остальные поля ...
    ssh_target: root@192.168.1.10:/etc/nebula
```

Формат: `user@IP:/путь/куда/класть`. Если поля нет — узел не деплоится, конфиги только в `output/`.

> **Важно:** `ssh_target` работает **только с SSH-ключами** (без пароля).
> Настрой ключи заранее:
> ```bash
> ssh-keygen -t ed25519
> ssh-copy-id root@192.168.1.10
> ```
> Пароли в конфиг **нельзя** — это небезопасно. Если нужен пароль — используй `sshpass` вручную.

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
