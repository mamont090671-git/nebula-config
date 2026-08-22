---
plan: nebula-config-fixes
created: 2026-08-22
status: in_progress
priority: critical
---

# План исправлений nebula-config

## Выполнено (текущая сессия)

### ✅ Удаление бинарников из репозитория
- Удалены из git: `for-all/nebula`, `for-all/nebula-cert`, `nebula-cert` (дубликат)
- `output/`, `__pycache__/` уже в `.gitignore`
- Создан `setup-binaries.sh` — скачивает бинарники из `slackhq/nebula` releases (tar.gz, распаковка)
- Поддержка архитектур: x86_64 → amd64, aarch64/arm64 → arm64
- Коммиты: ec67db7, e1b2b51

### ✅ Обновление README.md
- Структура проекта приведена в соответствие с реальностью (убраны несуществующие папки, output/, бинарники)
- Удалена секция "Генерация сертификатов" (дублирует документацию генератора)
- Добавлено примечание про `setup-binaries.sh`
- Обновлены инструкции решения проблем
- Коммит: 1761210

### ✅ Пуш на GitHub
- `74eb7f8..1761210 master -> master`

---

## Выполнено (предыдущие сессии)

### Фаза 1: Критические (исправлены)

#### 1.1 Обработать relay_servers в generate_configs.py ✅
**Результат:** Функция `build_relays_servers()` + параметр `relay_servers` в `render_config()`. Шаблон содержит `# RELAYS` placeholder. Сгенерированный конфиг содержит:
```yaml
relays:
  - "192.168.10.101"
```

#### 1.2 am_relay в конфиге лайтхауса ✅
**Результат:** `am_relay: true` вставляется в конфиг через `# AM_RELAY_PLACEHOLDER` → `am_relay: true`.

#### 1.3 use_relays: false на relay-сервере ✅
**Результат:** Для relay-лайтхауса `use_relays: false`, для NAT-хостов `use_relays: true`, для публичных `use_relays: false`.

### Фаза 2: Исправления генератора

#### 2.1 initiating_version: 2 — ОТМЕНЕНО ❌
Бессмыслен для чистой v2 сети.

#### 2.2 preferred_ranges ✅
Добавлено в оба шаблона.

#### 2.3 tunnels.drop_inactive ✅
Добавлено в оба шаблона.

#### 2.4 Убрать дубликат firewall ✅
Удалён.

### Фаза 3: Прочие исправления

#### 3.1 Безопасная замена имени сертификата ✅
`{{HOST_NAME}}` вместо `GPD_win_4`.

#### 3.2 Inline CA ✅
`build_inline_ca_block()` + `ca_pem` в master-конфе.

#### 3.3 Key-based signing ✅
Параметр `in_pub` + `-in-pub` в команде.

---

## ⬜ Следующие задачи (по предложениям)

### 🔴 P1 — Безопасность ✅ ВЫПОЛНЕНО

#### 1.1 ca_key_path — оффлайн CA ✅
**Выполнено:** Добавлено поле `ca_key_path` в `config-nebula.yaml`. Генератор читает его и передаёт во внешние функции. Если ключ задан — используется для подписи напрямую, `ca.key` не копируется в `output/ca/`.
**Результат:** External CA key passed to `generate_node_certificate()` via `write_config()`. No `ca.key` copy to output when `ca_key_path` is set.

#### 1.2 Харденить nebula_service.sh ✅
**Выполнено:** `nebula_service.sh` обновлён:
- Пользователь `nebula` (не root)
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `ProtectSystem=strict`, `ProtectHome=true`, `NoNewPrivileges=true`
- `ReadWritePaths=/etc/nebula` для записи конфига
- `useradd --system` для создания пользователя

### 🟠 P2 — Надёжность кода

#### 2.1 Pydantic для валидации конфига
**Проблема:** Валидация написана на чистом Python, сложно поддерживать при усложнении схемы.
**Решение:** Описать схему `config-nebula.yaml` через Pydantic — CIDR-проверка IP, диапазон порта 0-65535, обязательные поля.

#### 2.2 ipaddress stdlib
**Проблема:** static_host_map требует чистый IP без маски `/24`, пользователь дублирует данные.
**Решение:** `str(ipaddress.ip_interface("192.168.10.100/24").ip)` — автоотсечение маски.

### 🟡 P3 — Удобство

#### 3.1 --push: автоматическая доставка
**Проблема:** Пользователь вручную копирует конфиги на хосты.
**Решение:** Добавить поле `ssh_target: user@server-ip:/etc/nebula/` в конфиг. Флаг `--push` — scp/paramiko + перезапуск nebula.

#### 3.2 --ansible-inventory
**Проблема:** Нет интеграции с Ansible.
**Решение:** Флаг `--ansible-inventory` — преобразование в динамический инвентарь JSON/YAML.

### 🟢 P4 — DevOps

#### 4.1 pytest
**Проблема:** Нет автоматических тестов.
**Решение:** 2-3 теста: валидация конфига, ошибка relay для NAT, структура сгенерированного YAML.

#### 4.2 GitHub Actions CI
**Проблема:** Нет CI.
**Решение:** `.github/workflows/ci.yml` — black/flake8/ruff + pytest на каждый пуш.
