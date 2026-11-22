# Changelog

Все значимые изменения проекта.


---

## [2026-11-22] — Аудит и исправления (30 коммитов)

### Безопасность

#### Удаление `shell=True` (command injection prevention)
- `deploy_binaries`: ssh_target больше не подставляется в f-string (было `ssh "{ssh_target}"`)
- `deploy_configs`: hash check, test_cmd, rollback_cmd — все через list args
- `detect_remote_arch`: вместо `f'ssh ...'` → `["ssh", "-o", ..., ssh_target, "uname -m"]`
- `get_latest_release`: gh/curl через list args вместо shell=True
- `deploy_service`: heredoc → subprocess stdin (без shell=True)
- `deploy_binaries`: mktemp вместо `/tmp/` (symlink attack fix)

#### Валидация данных
- `ssh_target` формат: `user@host:/abs/path` (regex validation)
- `relay_servers` IP валидация (IPv4 + IPv6)
- `public_ip` поддержка IPv6 (ip_address вместо IPv4Address)

#### Обработка ошибок CA
- external_ca_key + отсутствующий ca.crt → exit с ошибкой (не auto-generate)
- ca_key чтение с try/except FileNotFoundError/PermissionError

### Исправления багов

- **--renew-expiring**: node_name = crt_file.parent.name (ключ YAML), а не crt_file.stem
- **--renew-expiring**: работает без --check-certs
- **--renew-expiring**: external_ca_key передается во все write_config()
- **in_pub**: поддержка dict {node_name: path} через resolve_in_pub()
- **deploy_configs**: бэкап config.yaml.bak ДО scp (не после)
- **deploy_binaries**: атомарная замена через `mv -f` (Text file busy fix)
- **nebula_service.sh**: синхронизация systemd unit с templates/nebula.service
- **nebula_service.sh**: GitHub API download URL вместо жёсткой ссылки
- **nebula_service.sh**: удаление дублирующего command -v
- **nebula_service.sh**: опциональное копирование ca.crt
- **deploy_configs**: локальная валидация config.yaml через `nebula -test`

### Очистка мёртвого кода

- Удалён compute_remote_file_hash() (не использовался)
- Удалён мёртвый nebula_test (заменён nebula_bin)
- Убраны дублирующиеся load_config() вызовы (было 4, осталось 1)
- Убран unused import validate_config_safe (добавлен заново в правильном месте)

### Форматирование

- ruff format/lint: все ошибки исправлены
- resolve_in_pub helper для in_pub dict/string

### Файлы

- Создан `templates/nebula.service` — единый источник systemd unit
- Удалён bug.md

---
---

## [2026-06-18] — Аудит и обновление документации

### Исправления кода

#### Удаление мёртвого кода в `deploy_configs()`
- Удалена переменная `has_critical` — не использовалась (lint F841)
- Удалена переменная `critical_files` — не использовалась (lint F841)
- Упрощён цикл проверки хэшей: без лишней guard-переменной

### Документация

#### README.md / README-EN.md
- Добавлена секция «Дополнительные флаги» / «Additional Flags» — все флаги из `--help`
- Добавлен `--cert-path` в оба README
- Исправлено описание `ca_pem` в `config-nebula.example.yaml`: raw PEM, не base64
- Удалено неиспользуемое поле `type: LH/HOST` из примеров конфига

### Зависимости

#### requirements.txt
- Удалён `validators>=0.34.0` — мёртвая зависимость (импорт идёт из локального `validators.py`, не из pip-пакета)

### Тесты

- Количество тестов осталось 31 (новых не добавлено)

---

## [2026-11-21] — Полный день работ

### Фичи

#### `--renew-expiring` — автоматический перевыпуск истекающих сертификатов
- Новый флаг `--renew-expiring` в `generate_configs.py`
- Находит сертификаты, истекающие в течение 30 дней (через `--check-certs`)
- Удаляет старые `.crt`/`.key` для каждого узла с истекающим сертификатом
- Перезапускает генерацию сертификата через `generate_node_certificate`
- Перезаписывает конфиги с обновлённым inline CA
- Выводит отчёт: сколько сертификатов перевыпущено

#### `--dry-run` для `--push` — предпросмотр деплоя
- Флаг `--dry-run` показывает, какие узлы и файлы будут изменены
- Без фактического деплоя — только вывод в консоль
- Позволяет проверить результат перед реальным деплоем

### Безопасность деплоя

#### `nebula_service.sh` — backup + валидация + авто-откат
- Перед заменой конфига создаётся бэкап `config.yaml.bak`
- Запуск `nebula -test` перед перезапуском сервиса
- Если тест не прошёл — авто-откат из бэкапа, nebula **не стартует**
- Сервер не потеряет связь при ошибке в конфиге

### CI/CD

#### Обновление GitHub Actions
- `actions/checkout@v4` → `@v5` (Node.js 20 → 22+)
- `actions/setup-python@v5` → `@v6` (Node.js 20 → 22+)
- Запинена версия ruff: `ruff==0.17.6` (предотвращает дрифт форматирования)

#### Исправление CI
- Тесты больше не пропускаются при отсутствии `config-nebula.yaml`
- Исправлен парсинг дат в `--check-certs`
- Удалены бинарники `nebula`/`nebula-cert` из git
- `.gitignore` обновлён для бинарников Nebula
- Упрощён workflow: убрана зависимость lint от test, добавлен `pyyaml`
- Закомментирован step `validators.py` (требует реальный конфиг)

### Форматирование кода
- `ruff format` — исправлены long lines в `generate_configs.py`
- `ruff F541` — удаленыunnecessary f-strings в dry-run output
- Форматирование применено ко всем файлам проекта

### Документация

#### README.md / README-EN.md
- Переименован раздел `Quick Start` → `Installation`
- Добавлены разделы:
  - `--dry-run` предпросмотр деплоя
  - Безопасность деплоя (backup, валидация, авто-откат)
  - `ssh_target` — требование SSH-ключей, без паролей
- Раскомментированы примеры `ssh_target` в `config-nebula.yaml`
- Исправлено использование `--only-lights` в README-EN
- Удалены дублирующиеся/бессодержательные секции

### Инвентарь и валидация
- `nebula_inventory.py` — обновлён для соответствия новому формату конфига
- `validators.py` — адаптирован под новые валидации

---

## Итого за день: 20 коммитов

| Категория | Кол-во коммитов |
|-----------|-----------------|
| Фичи      | 2               |
| Безопасность | 1            |
| CI/CD     | 6               |
| Форматирование | 3          |
| Документация | 5            |
| Прочее    | 3               |
