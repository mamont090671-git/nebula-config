---
plan: nebula-config-fixes
created: 2026-08-22
status: completed
priority: critical
---

# План исправлений nebula-config

## Фаза 1: Критические (блокируют работу relay)

### 1.1 Обработать relay_servers в generate_configs.py
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Добавить чтение relay_servers и вставку relays: секции в шаблон хоста.
**Результат:** Добавлена функция `build_relays_servers()` и параметр `relay_servers` в `render_host_config()`. Шаблон `host/config.yaml` содержит `{{RELAYS}}` placeholder. В `main()` добавлено чтение `relay_servers` из master-конфа и передача в `render_host_config()`. Сгенерированный конфиг содержит:
```yaml
relays:
  - "192.168.10.101"
```
Проверено: работает корректно для всех хостов (NL-H с port 4242 и gpd с port 0).

### 1.2 am_relay в сгенерированном конфиге лайтхауса
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Добавить передачу am_relay в render_lighthouse_config().
**Результат:** В `render_lighthouse_config()` добавлена обработка `am_relay:` — значение берётся из master-конфа (`lh_data.get('am_relay', False)`). Для light-1: `am_relay: true`.

### 1.3 use_relays: false на relay-сервере
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** В render_lighthouse_config() установить use_relays: false для relay-узлов.
**Результат:** В `render_lighthouse_config()` добавлена логика: если `am_relay: true` (relay-сервер), то `use_relays: false`. Иначе `use_relays: true`. Для light-1: `use_relays: false`.

---

## Фаза 2: Высокий приоритет

### 2.1 initiating_version: 2
**Статус: ОТМЕНЕНО** ❌
**Задача:** В render_host_config() добавить `initiating_version: 2` при генерации v2.
**Причина отмены:** initiating_version применяется ТОЛЬКО если оба v1 и v2 сертификата настроены одновременно. В нашем случае используется только v2, этот параметр бессмыслен. Документация Nebula подтверждает: "This setting only applies if both a v1 and a v2 certificate are configured". Удалён из шаблона.

### 2.2 Добавить preferred_ranges
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Добавить preferred_ranges в шаблоны.
**Результат:** Добавлено `preferred_ranges: ["192.168.10.0/24"]` в оба шаблона (host и lighthouse). Приоритет — локальная сеть 192.168.10.0/24.

### 2.3 Добавить tunnels.drop_inactive
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Добавить `drop_inactive: true` в tun секцию шаблонов.
**Результат:** Добавлено `tunnels: { drop_inactive: true, inactivity_timeout: 10m }` в оба шаблона (host и lighthouse). Активны для Nebula >= v1.9.6.

### 2.4 Убрать дубликат firewall rule
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Удалить дубликат в шаблоне хоста.
**Результат:** Удалена вторая identical rule (port:any, proto:any, host:any) из inbound секции. Осталась одна.

---

## Фаза 3: Средний приоритет

### 3.1 Безопасная замена имени сертификата
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Заменить на переменную или регулярное выражение.
**Результат:** В шаблоне `GPD_win_4.crt/key` заменено на `{{HOST_NAME}}.crt/key`. Генератор теперь заменяет `{{HOST_NAME}}` на имя хоста при генерации. Проверено — вывод корректный, GPD_win_4 полностью убран.

### 3.2 Добавить inline CA
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Поддержка PEM inline в конфиге.
**Результат:** В `config-nebula.yaml` добавлено поле `ca_pem`. В генераторе добавлена функция `build_inline_ca_block()` — строит YAML block scalar из CA PEM. В `render_host_config()` и `render_lighthouse_config()` добавлена обработка: если `ca_pem` не пустой, `pki.ca` заменяется на inline block. В `main()` добавлено чтение `ca_pem` и передача в `render_host_config()`/`render_lighthouse_config()`.

### 3.3 Добавить key-based signing
**Статус: ВЫПОЛНЕНО** ✅
**Задача:** Добавить поддержку nebula-cert sign -in-pub.
**Результат:** В `config-nebula.yaml` добавлено поле `in_pub` (публичный адрес для -in-pub). В `generate_node_certificate()` добавлен параметр `in_pub` — если установлен, к команде добавляется `-in-pub <addr>`. `in_pub` передан через `write_config()`, `generate_all_host_certs()` и `main()`.

---

## Проверки после выполнения

1. python3 generate_configs.py --generate-ca
2. python3 generate_configs.py
3. Проверить output/*/config.yaml:
   - relays: секция есть
   - am_relay: true на lh
   - use_relays: false на lh
   - initiating_version: 2
   - preferred_ranges есть
   - drop_inactive: true
   - нет дубликатов firewall
   - static_host_map заполнен
4. Проверить IP-конфликты
