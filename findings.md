# Findings: Multi-network Nebula Config

## Исследование текущего проекта

### Файловая структура
```
nebula-config/
├── generate_configs.py          # 823 строки — основной генератор
├── validators.py                # 214 строк — валидация через dataclasses
├── nebula_inventory.py          # 94 строки — Ansible inventory
├── generate_deploy.sh           # 56 строк — генерация deploy.sh
├── setup-binaries.sh            # установка бинарников nebula/nebula-cert
├── config-nebula.yaml           # мастер-конфиг (103 строки, НЕ МЕНЯТЬ)
├── templates/config.yaml        # шаблон (76 строк, статический dev/addr)
├── tests/test_config.py         # 252 строки, 23 теста, 2 падают (yaml)
└── .github/workflows/ci.yml     # ruff + pytest
```

### Текущий формат config-nebula.yaml (одна сеть)
```yaml
net-name: y-net
dev: nebula2
relay_servers: [...]
ca_pem: ""
in_pub: ""
ca_key_path: ""
lighthouse:
  RU: {groups, nebula_ip, port, public_ip, am_relay, type}
hosts:
  LA-H: {groups, nebula_ip, port, public_ip, type}
  ...
```

### Проблемы для multi-network
1. **Один CA** — сейчас `output/ca/ca.key` и `ca.crt` для всех узлов
2. **Один tun** — шаблон жёстко `dev: nebula1`, `addr` берётся из `nebula_ip.ipv4`
3. **Один preferred_ranges** — жёстко `192.168.10.0/24` в шаблоне
4. **Нет имени сети** в узлах — нет way отличить сеть
5. **Ansible inventory** — все узлы в одной группе `Nebula`
6. **Тесты падают** — 2 теста из 23 из-за `import yaml` (PyYAML не в requirements)

### Архитектурное решение: flat list сетей

```yaml
networks:
  y-net:
    net-name: y-net
    dev: nebula2
    subnet: 192.168.11.0/24
    relay_servers:
      - 192.168.11.101
    ca_pem: ""
    lighthouse:
      RU: {groups, nebula_ip, port, public_ip, am_relay}
    hosts:
      LA-H: {groups, nebula_ip, port, public_ip}
      ...
  x-net:
    net-name: x-net
    dev: nebula1
    subnet: 192.168.10.0/24
    relay_servers:
      - 192.168.10.101
    ca_pem: ""
    lighthouse:
      light-1: {groups, nebula_ip, port, public_ip, am_relay}
    hosts:
      server-1: {groups, nebula_ip, port, public_ip}
      ...
```

### Ключевые решения
- **Каждая сеть = отдельный CA** (отдельная папка `output/<net-name>/ca/`)
- **dev и subnet** задаются на уровне сети, а не генерируются
- **preferred_ranges** в шаблоне берётся из `subnet` текущей сети
- **output/<net-name>/<node>/** — изоляция по сети
- **--net NAME** фильтр для выбора сети
- **compatibility**: если `networks:` нет, использовать legacy формат (backwards compat)
