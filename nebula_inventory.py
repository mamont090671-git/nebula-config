#!/usr/bin/env python3
"""
Динамический инвентарь Ansible для Nebula.
Читает config-nebula.yaml и выдаёт JSON inventory.

Использование:
  ansible-inventory --list -i nebula_inventory.py
  ansible-playbook -i nebula_inventory.py deploy.yml --limit Nebula
  ansible-playbook -i nebula_inventory.py deploy.yml --limit home
"""

import json
import sys
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config-nebula.yaml"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"Ошибка: {CONFIG_PATH} не найден", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def build_inventory(config):
    lighthouses = config.get('lighthouse', {})
    hosts = config.get('hosts', {})
    
    all_nodes = {}
    for name, data in lighthouses.items():
        all_nodes[name] = {**data, '_type': 'lighthouse'}
    for name, data in hosts.items():
        all_nodes[name] = {**data, '_type': 'host'}
    
    inventory = {
        '_meta': {'hostvars': {}},
        'Nebula': {
            'hosts': list(all_nodes.keys()),
            'vars': {'nebula_network': config.get('net-name', 'nebula-net')}
        },
        'all': {'children': ['Nebula']}
    }
    
    for name, data in all_nodes.items():
        nebula_ip = data.get('nebula_ip', {})
        public_ip = data.get('public_ip')
        port = data.get('port', '4242')
        
        hostvars = {
            'nebula_type': data.get('_type'),
            'nebula_group': data.get('groups', 'home'),
            'nebula_port': port,
            'nebula_ipv4': nebula_ip.get('ipv4', ''),
            'nebula_ipv6': nebula_ip.get('ipv6', ''),
        }
        
        if public_ip:
            hostvars['ansible_host'] = public_ip
        elif nebula_ip.get('ipv4'):
            hostvars['ansible_host'] = nebula_ip['ipv4'].split('/')[0]
        
        # Группы из конфига -> группы Ansible
        for g in str(data.get('groups', 'home')).split(','):
            g = g.strip()
            if g and g not in inventory:
                inventory[g] = {'hosts': [], 'vars': {}}
            if name not in inventory[g]['hosts']:
                inventory[g]['hosts'].append(name)
        
        inventory['_meta']['hostvars'][name] = hostvars
    
    return inventory


if __name__ == '__main__':
    config = load_config()
    inventory = build_inventory(config)
    
    if '--list' in sys.argv:
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
    elif '--host' in sys.argv:
        host_index = sys.argv.index('--host')
        if host_index + 1 < len(sys.argv):
            host_name = sys.argv[host_index + 1]
            hostvars = inventory['_meta']['hostvars'].get(host_name, {})
            print(json.dumps(hostvars, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({}))
    else:
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
