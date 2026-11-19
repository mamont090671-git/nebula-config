# Task Plan: Multi-network Nebula Config Generator

## Goal

Расширить nebula-config для поддержки нескольких независимых Nebula-сетей в одном `config-nebula.yaml`. Каждая сеть = отдельный CA, tun-интерфейс, подсеть. Узлы и лайтхаусы могут участвовать в нескольких сетях одновременно. Без флагов: `python3 generate_configs.py` делает всё.

## Next Step

План утверждён пользователем → фаза 1: формат config.

## Current Phase

Phase 1: Формат config

## Phases

### Phase 1: Формат config-nebula.yaml

- [ ] Определить формат `networks:` с поддержкой legacy
- [ ] Определить правила пересечения узлов/лайтхаусов между сетями
- [ ] Определить структуру `output/<net>/<node>/`
- [ ] Определить как задаётся маска в `nebula_ip`
- [ ] Записать формат в config-nebula.yaml.example
- **Status:** in_progress

### Phase 2: Фикс тестов

- [ ] Добавить PyYAML в requirements.txt
- [ ] Зафиксить 2 failing теста (import yaml)
- [ ] Убедиться все 23 теста проходят
- **Status:** pending

### Phase 3: Генератор (generate_configs.py)

- [ ] `load_config()` — поддержка `networks:` + legacy fallback
- [ ] Валидация: нет дубликатов IP между сетями
- [ ] Генерация CA per-network: `output/<net>/ca/`
- [ ] Генерация сертификатов per-network
- [ ] Генерация конфигов per-network: `output/<net>/<node>/config.yaml`
- [ ] Копирование файлов in network-specific output dir
- [ ] Деплой per-network: `systemctl restart nebula` для каждого экземпляра
- [ ] Верификация per-network
- **Status:** pending

### Phase 4: Шаблон (templates/config.yaml)

- [ ] Добавить `{{NETWORK_DEV}}` вместо жёсткого `nebula1`
- [ ] Добавить `{{NETWORK_SUBNET}}` для `preferred_ranges`
- [ ] Проверить что mask в `nebula_ip` не ломает рендеринг
- **Status:** pending

### Phase 5: Валидаторы (validators.py)

- [ ] Dataclass `NetworkConfig` с полями: net_name, dev, subnet, relay_servers, lighthouse, hosts
- [ ] Валидация: subnet — валидный CIDR
- [ ] Валидация: dev не пустой
- [ ] Валидация: нет дубликатов IP между всеми сетями
- [ ] Валидация: каждый node в каждой сети имеет nebula_ip
- [ ] Legacy fallback: один legacy config → один network
- **Status:** pending

### Phase 6: Инвентарь (nebula_inventory.py)

- [ ] Чтение `networks:` из config
- [ ] Группы: `<net>-nodes`, `<net>-lighthouses`
- [ ] Groups из конфига → `<net>-<group>`
- [ ] hostvars: `nebula_network`, `nebula_dev`, `nebula_subnet`
- **Status:** pending

### Phase 7: Деплой (generate_deploy.sh)

- [ ] Генерация deploy.sh per-network
- [ ] Структура: `output/<net>/<node>/deploy.sh`
- **Status:** pending

### Phase 8: Документация и CI

- [ ] README.md — пример multi-network config
- [ ] README.md — описание формата networks:
- [ ] README.md — пример с общим лайтхаусом и общим хостом
- [ ] CI — PyYAML в dependencies
- **Status:** pending

## Decisions Made

| Решение | Обоснование |
|---------|-------------|
| Формат: flat `networks:` dict | Простой, читаемый, backwards compatible |
| Маска в nebula_ip = маска подсети | Как сейчас в проекте, не ломает генератор |
| output/<net>/<node>/ | Изоляция по сети, проще деплой |
| CA per-network | Каждая сеть — отдельная PKI |
| Без флагов, всё через конфиг | Простой запуск: `python3 generate_configs.py` |
| Legacy fallback | Не ломать существующий конфиг |

## Errors Encountered

| Ошибка | Попытка | Решение |
|--------|---------|---------|
| | | |

## Notes

- config-nebula.yaml НЕ МЕНЯТЬ — пользователь запретил
- Все имена узлов уникальны (один физический сервер = одно имя)
- Лайтхаус может быть в нескольких сетях (один сервер, несколько nebula-экземпляров)
- Хост может быть в нескольких сетях (один сервер, несколько tun)
- Каждая сеть = отдельный tun (dev) = отдельная подсеть (subnet)
