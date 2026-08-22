#!/usr/bin/env python3
"""
Генератор конфигураций Nebula VPN
Читает config-nebula.yaml и создаёт конфигурационные файлы для узлов и маяков
с единого шаблона templates/config.yaml.

Использование:
  python3 generate_configs.py                                    # Все узлы и маяки (по умолчанию)
  python3 generate_configs.py --all                              # Все узлы и все маяки (явный флаг)
  python3 generate_configs.py --host HOST1 HOST2                 # Только указанные узлы + все маяки
  python3 generate_configs.py --light LH1 LH2                    # Все узлы + указанные маяки
  python3 generate_configs.py --only-hosts --host A B            # Только узлы A, B (без маяков)
  python3 generate_configs.py --only-lights --light X Y          # Только маяки X, Y (без узлов)
  python3 generate_configs.py --generate-ca                      # Сгенерировать CA-сертификат
  python3 generate_configs.py --generate-host-certs              # Сгенерировать все сертификаты узлов
"""

import yaml
import sys
import argparse
import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MASTER_CONFIG = SCRIPT_DIR / "config-nebula.yaml"
TEMPLATE = SCRIPT_DIR / "templates/config.yaml"
FOR_ALL_DIR = SCRIPT_DIR / "for-all"
OUTPUT_DIR = SCRIPT_DIR / "output"


def load_config():
    if not MASTER_CONFIG.exists():
        print(f"Ошибка: Конфигурация не найдена: {MASTER_CONFIG}", file=sys.stderr)
        sys.exit(1)
    
    with open(MASTER_CONFIG, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_template():
    if not TEMPLATE.exists():
        print(f"Ошибка: Шаблон не найден: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)
    
    with open(TEMPLATE, 'r', encoding='utf-8') as f:
        return f.read()


def build_static_host_map_for_client(lighthouses):
    """Строит static_host_map для узла-клиента (список всех маяков с публичными IP:Port)"""
    lines = ['static_host_map:']
    lines.append('  # Внутренний IPv4 маяка: [Публичный_IP:Порт]')
    lines.append('  # Внутренний IPv6 маяка: [Публичный_IP:Порт]')
    
    for lh_name, lh_data in lighthouses.items():
        ipv4 = lh_data.get('nebula_ip', {}).get('ipv4', '').split('/')[0]
        ipv6 = lh_data.get('nebula_ip', {}).get('ipv6', '').split('/')[0]
        public_ip = lh_data.get('public_ip', '')
        port = lh_data.get('port', '')
        
        if ipv4 and public_ip and port:
            lines.append(f'  "{ipv4}": ["{public_ip}:{port}"]')
        if ipv6 and public_ip and port:
            lines.append(f'  "{ipv6}": ["{public_ip}:{port}"]')
    
    return '\n'.join(lines)


def build_static_host_map_for_lighthouse(lighthouses, current_name):
    """Строит static_host_map для маяка (только другие маяки с IPv4:Port)"""
    lines = ['static_host_map:']
    has_entries = False
    
    for lh_name, lh_data in lighthouses.items():
        if lh_name != current_name:
            ipv4 = lh_data.get('nebula_ip', {}).get('ipv4', '').split('/')[0]
            ipv6 = lh_data.get('nebula_ip', {}).get('ipv6', '').split('/')[0]
            public_ip = lh_data.get('public_ip', '')
            port = lh_data.get('port', '')
            
            if ipv4 and public_ip and port:
                lines.append(f'  "{ipv4}": ["{public_ip}:{port}"]')
                has_entries = True
            if ipv6 and public_ip and port:
                lines.append(f'  "{ipv6}": ["{public_ip}:{port}"]')
                has_entries = True
    
    return '\n'.join(lines) if has_entries else None


def build_lighthouse_hosts_for_client(lighthouses):
    """Строит hosts для узла-клиента (список всех маяков)"""
    lines = []
    for lh_name, lh_data in lighthouses.items():
        ipv6 = lh_data.get('nebula_ip', {}).get('ipv6', '').split('/')[0]
        ipv4 = lh_data.get('nebula_ip', {}).get('ipv4', '').split('/')[0]
        if ipv6:
            lines.append(f'    - "{ipv6}"')
        if ipv4:
            lines.append(f'    - "{ipv4}"')
    return '\n'.join(lines)


def build_lighthouse_hosts_for_lighthouse(lighthouses, current_name):
    """Строит hosts для маяка (только другие маяки)"""
    lines = []
    for lh_name, lh_data in lighthouses.items():
        if lh_name != current_name:
            ipv6 = lh_data.get('nebula_ip', {}).get('ipv6', '').split('/')[0]
            ipv4 = lh_data.get('nebula_ip', {}).get('ipv4', '').split('/')[0]
            if ipv6:
                lines.append(f'    - "{ipv6}"')
            if ipv4:
                lines.append(f'    - "{ipv4}"')
    return '\n'.join(lines) if lines else None


def build_relays_servers(relay_servers_list):
    """Строит relays: секцию из списка relay-серверов"""
    if not relay_servers_list:
        return '  # Нет relay-серверов'
    lines = []
    for ip in relay_servers_list:
        lines.append(f'  - "{ip}"')
    return '\n'.join(lines)


def build_inline_ca_block(ca_pem):
    """Строит pki.ca секцию с inline PEM"""
    if not ca_pem:
        return None
    lines = ['ca: |']
    for line in ca_pem.split('\n'):
        lines.append(f'  {line}')
    return '\n'.join(lines)


def render_config(template, node_name, node_data, node_type, lighthouses, relay_servers=None, ca_pem=None, extra_inbound_rules=None):
    """Единственная функция рендеринга для любого типа узла"""
    
    is_lighthouse = node_type == 'lighthouse'
    is_relay = is_lighthouse and node_data.get('am_relay', False)
    is_single_lighthouse = len(lighthouses) == 1
    
    # Строим секции
    if is_lighthouse:
        static_map = build_static_host_map_for_lighthouse(lighthouses, node_name)
        lh_hosts = build_lighthouse_hosts_for_lighthouse(lighthouses, node_name)
        am_relay_val = str(node_data.get('am_relay', False)).lower()
        use_relays_val = "false" if is_relay else "true"
    else:
        static_map = build_static_host_map_for_client(lighthouses)
        lh_hosts = build_lighthouse_hosts_for_client(lighthouses)
        am_relay_val = 'false'
        use_relays_val = 'true'
    
    relays_val = build_relays_servers(relay_servers) if not is_relay else '  # Нет relay-серверов'
    listen_host = '"[::]"' if not is_lighthouse else '"::"'
    listen_port = str(node_data.get('port', '4242'))
    
    # Inline CA
    inline_ca = build_inline_ca_block(ca_pem)
    
    # Заменяем плейсхолдеры
    result = template
    result = result.replace('{{HOST_NAME}}', node_name)
    result = result.replace('{{STATIC_HOST_MAP}}', static_map or '# Нет static_host_map')
    result = result.replace('{{LH_HOSTS}}', lh_hosts or '    # Нет других маяков')
    result = result.replace('{{AM_RELAY}}', am_relay_val)
    result = result.replace('{{USE_RELAYS}}', use_relays_val)
    result = result.replace('{{RELAYS}}', relays_val)
    result = result.replace('{{LISTEN_HOST}}', listen_host)
    result = result.replace('{{LISTEN_PORT}}', listen_port)
    result = result.replace('{{FIREWALL_EXTRA_INBOUND}}', extra_inbound_rules or '')
    
    # Inline CA замена
    if inline_ca:
        result = result.replace(
            'ca: /etc/nebula/ca.crt',
            inline_ca
        )
    
    return result


def verify_generated_configs(config, lighthouses, hosts, relay_servers):
    """Проверка сгенерированных конфигов на корректность."""
    errors = []
    warnings = []
    
    # 1. Проверка relay_servers не пусты для NAT-хостов
    if relay_servers:
        relay_ips = [r for r in relay_servers if r]
        if not relay_ips:
            errors.append("relay_servers пустой — NAT-хосты не будут знать relay-сервер")
    else:
        nat_hosts = [name for name, data in hosts.items() if str(data.get('port', '4242')) == '0']
        if nat_hosts:
            warnings.append(f"relay_servers не указан, но есть NAT-хосты с port 0: {', '.join(nat_hosts)}")
    
    # 2. Проверка port 0 хостов — use_relays: true
    for host_name, host_data in hosts.items():
        port = str(host_data.get('port', '4242'))
        if port == '0':
            config_file = OUTPUT_DIR / host_name / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    content = f.read()
                if 'use_relays: true' not in content:
                    errors.append(f"{host_name} (port 0): use_relays: true отсутствует в конфиге")
                if 'relay:' not in content:
                    errors.append(f"{host_name} (port 0): секция relay: отсутствует в конфиге")
                if 'use_relays: false' in content:
                    errors.append(f"{host_name} (port 0): use_relays: false вместо true")
    
    # 3. Проверка relay-лайтхауса — am_relay: true, use_relays: false
    for lh_name, lh_data in lighthouses.items():
        if lh_data.get('am_relay', False):
            config_file = OUTPUT_DIR / lh_name / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    content = f.read()
                if 'am_relay: true' not in content:
                    errors.append(f"{lh_name} (am_relay): am_relay: true отсутствует в конфиге")
                if 'use_relays: false' not in content:
                    errors.append(f"{lh_name} (am_relay): use_relays: false отсутствует в конфиге")
    
    # 4. Проверка static_host_map на клиентах
    for host_name in hosts:
        config_file = OUTPUT_DIR / host_name / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r') as f:
                content = f.read()
            if 'static_host_map:' not in content:
                errors.append(f"{host_name}: static_host_map отсутствует в конфиге")
            else:
                has_lh_map = False
                for lh_name in lighthouses:
                    lh_ip = lighthouses[lh_name].get('nebula_ip', {}).get('ipv4', '').split('/')[0]
                    if lh_ip and lh_ip in content:
                        has_lh_map = True
                        break
                if not has_lh_map:
                    warnings.append(f"{host_name}: static_host_map не содержит IPv4 лайтхауса")
    
    # 5. Проверка IPv6 hosts на клиентах
    for host_name in hosts:
        config_file = OUTPUT_DIR / host_name / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r') as f:
                content = f.read()
            lh_match = content.find('lighthouse:')
            if lh_match != -1:
                hosts_section_start = content.find('hosts:', lh_match)
                if hosts_section_start != -1:
                    hosts_section = content[hosts_section_start + 7:]
                    hosts_lines = hosts_section.split('\n')[:20]
                    hosts_list = '\n'.join(hosts_lines)
                    for lh_name, lh_data in lighthouses.items():
                        ipv6 = lh_data.get('nebula_ip', {}).get('ipv6', '').split('/')[0]
                        if ipv6 and ipv6 not in hosts_list:
                            warnings.append(f"{host_name}: hosts секция lighthouse не содержит IPv6 {ipv6} ({lh_name})")
    
    # Итог
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СГЕНЕРИРОВАННЫХ КОНФИГОВ")
    print("=" * 60)
    
    if warnings:
        print(f"\nПредупреждения ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
    
    if errors:
        print(f"\nОшибки ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        print("\nРезультат: НЕ ПРОЙДЕНО — исправьте указанные ошибки")
        return False
    else:
        if warnings:
            print("\nРезультат: ПРОЙДЕНО С ПРЕДУПРЕЖДЕНИЯМИ")
        else:
            print("\nРезультат: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ✓")
        return True


def copy_for_all_files(node_dir):
    """Копирует файлы из for-all/ в node_dir"""
    if not FOR_ALL_DIR.exists():
        print(f"  Внимание: Папка for-all/ не найдена, файлы не копируются")
        return
    
    files_copied = []
    for item in FOR_ALL_DIR.iterdir():
        if item.is_file():
            dest = node_dir / item.name
            shutil.copy2(item, dest)
            files_copied.append(item.name)
    
    if files_copied:
        print(f"  Скопировано: {', '.join(files_copied)}")


def copy_ca_to_node(node_dir, ca_crt_path):
    """Копирует CA-сертификат в node_dir"""
    if not ca_crt_path.exists():
        print(f"  Внимание: CA-сертификат не найден: {ca_crt_path}")
        return
    
    dest = node_dir / "ca.crt"
    shutil.copy2(ca_crt_path, dest)
    print(f"  CA: {dest.name} скопирован")


def generate_node_certificate(node_name, node_data, ca_dir, nebula_cert_path, in_pub=None):
    """Генерация сертификата для узла/маяка"""
    ipv4 = node_data.get('nebula_ip', {}).get('ipv4', '')
    ipv6 = node_data.get('nebula_ip', {}).get('ipv6', '')
    
    ip_params = []
    if ipv4:
        ip_params.append(ipv4)
    if ipv6:
        ip_params.append(ipv6)
    
    if not ip_params:
        print(f"  Ошибка: нет nebula_ip для узла {node_name}", file=sys.stderr)
        return False, None
    
    ip_string = ','.join(ip_params)
    groups = node_data.get('groups', 'home')
    cert_name = node_data.get('name', node_name)
    
    node_dir = OUTPUT_DIR / node_name
    node_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        str(nebula_cert_path),
        "sign",
        "-name", cert_name,
        "-ip", ip_string,
        "-groups", groups,
        "-ca-crt", str(ca_dir / "ca.crt"),
        "-ca-key", str(ca_dir / "ca.key"),
        "-out-crt", str(node_dir / f"{cert_name}.crt"),
        "-out-key", str(node_dir / f"{cert_name}.key")
    ]
    
    if in_pub:
        cmd.extend(["-in-pub", in_pub])
        print(f"  Режим key-based signing: -in-pub {in_pub}")
    
    print(f"  Генерация сертификата для {node_name}...")
    print(f"    Имя: {cert_name}")
    print(f"    IP: {ip_string}")
    print(f"    Группы: {groups}")
    print(f"    Команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if (node_dir / f"{cert_name}.crt").exists() and (node_dir / f"{cert_name}.key").exists():
            print(f"✓ Сертификат создан: {node_dir / cert_name}.crt")
            print(f"  Ключ: {node_dir / cert_name}.key")
            return True, f"{cert_name}.crt"
        else:
            print(f"Ошибка: файлы сертификата не созданы", file=sys.stderr)
            return False, None
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации сертификата {node_name}: {e}", file=sys.stderr)
        if e.stderr:
            print(f"  STDERR: {e.stderr}", file=sys.stderr)
        return False, None
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return False, None


def write_config(node_name, config_content, ca_crt_path=None, generate_cert=True, in_pub=None):
    node_dir = OUTPUT_DIR / node_name
    node_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = node_dir / "config.yaml"
    
    if output_file.exists():
        backup = node_dir / f"{node_name}.yaml.backup"
        shutil.copy2(output_file, backup)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"✓ Создано: {output_file}")
    
    copy_for_all_files(node_dir)
    
    if ca_crt_path:
        copy_ca_to_node(node_dir, ca_crt_path)
    
    if generate_cert and ca_crt_path.exists():
        ca_dir = OUTPUT_DIR / "ca"
        config = load_config()
        node_data = config.get('hosts', {}).get(node_name) or config.get('lighthouse', {}).get(node_name)
        
        if node_data:
            nebula_cert_path = None
            if (SCRIPT_DIR / "for-all" / "nebula-cert").exists():
                nebula_cert_path = SCRIPT_DIR / "for-all" / "nebula-cert"
            else:
                nebula_cert_path = shutil.which("nebula-cert")
            
            if nebula_cert_path and ca_dir.exists():
                success, cert_file = generate_node_certificate(
                    node_name, node_data, ca_dir, nebula_cert_path, in_pub=in_pub
                )


def generate_ca(network_name, nebula_cert_path):
    """Генерация CA-сертификата"""
    ca_dir = OUTPUT_DIR / "ca"
    ca_dir.mkdir(parents=True, exist_ok=True)
    
    if not nebula_cert_path.exists():
        print(f"Ошибка: nebula-cert не найден по пути {nebula_cert_path}", file=sys.stderr)
        sys.exit(1)
    
    ca_key = ca_dir / "ca.key"
    ca_crt = ca_dir / "ca.crt"
    
    if ca_key.exists() and ca_crt.exists():
        print(f"CA уже существует в {ca_dir}/")
        return
    
    cmd = [
        str(nebula_cert_path),
        "ca",
        "-name", network_name,
        "-version", "2",
        "-out-key", str(ca_key),
        "-out-crt", str(ca_crt)
    ]
    
    print(f"Генерация CA для сети '{network_name}'...")
    print(f"  Команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if ca_key.exists() and ca_crt.exists():
            print(f"✓ CA создан в: {ca_dir}")
            print(f"  CA ключ: {ca_key}")
            print(f"  CA сертификат: {ca_crt}")
        else:
            print(f"Ошибка: файлы CA не созданы", file=sys.stderr)
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации CA: {e}", file=sys.stderr)
        if e.stderr:
            print(f"  STDERR: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


def generate_all_host_certs(config, nebula_cert_path, ca_dir, in_pub=None):
    """Генерация сертификатов для всех узлов и маяков"""
    if not ca_dir.exists():
        print(f"Ошибка: CA-сертификат не найден в {ca_dir}", file=sys.stderr)
        print("Сначала сгенерируйте CA: python3 generate_configs.py --generate-ca", file=sys.stderr)
        sys.exit(1)
    
    lighthouses = config.get('lighthouse', {})
    hosts = config.get('hosts', {})
    
    all_nodes = {}
    for lh_name, lh_data in lighthouses.items():
        all_nodes[lh_name] = lh_data
    for host_name, host_data in hosts.items():
        all_nodes[host_name] = host_data
    
    success_count = 0
    fail_count = 0
    
    print(f"\nГенерация сертификатов для всех узлов ({len(all_nodes)} шт.)")
    print("=" * 50)
    
    for node_name, node_data in all_nodes.items():
        success, _ = generate_node_certificate(node_name, node_data, ca_dir, nebula_cert_path, in_pub=in_pub)
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 50)
    print(f"Итого: {success_count} успешных, {fail_count} ошибок")
    
    return fail_count == 0


def main():
    parser = argparse.ArgumentParser(
        description='Генератор конфигураций Nebula VPN',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Генерация всех узлов и маяков (по умолчанию)
  python3 generate_configs.py
  
  # Явная генерация всех узлов и всех маяков
  python3 generate_configs.py --all
  
  # Только указанные узлы + все маяки
  python3 generate_configs.py --host NL-H RU
  
  # Все узлы + указанные маяки
  python3 generate_configs.py --light light-1
  
  # Только узлы NL-H и RU (без маяков)
  python3 generate_configs.py --only-hosts --host NL-H RU
  
  # Только маяки light-1 (без узлов)
  python3 generate_configs.py --only-lights --light light-1
  
  # Сгенерировать CA-сертификат
  python3 generate_configs.py --generate-ca
  
  # Сгенерировать сертификаты для всех узлов
  python3 generate_configs.py --generate-host-certs
        """
    )
    
    parser.add_argument('--host', nargs='+', metavar='HOST',
                        help='Имена узлов для генерации (по умолчанию все)')
    parser.add_argument('--light', nargs='+', metavar='LIGHT',
                        help='Имена маяков для генерации (по умолчанию все)')
    parser.add_argument('--all', action='store_true',
                        help='Явная генерация всех узлов и всех маяков (по умолчанию)')
    parser.add_argument('--only-hosts', action='store_true',
                        help='Генерировать только узлы (без маяков)')
    parser.add_argument('--only-lights', action='store_true',
                        help='Генерировать только маяки (без узлов)')
    parser.add_argument('--generate-ca', action='store_true',
                        help='Сгенерировать CA-сертификат')
    parser.add_argument('--generate-host-certs', action='store_true',
                        help='Сгенерировать сертификаты для всех узлов')
    parser.add_argument('--cert-path', type=str, default=None,
                        help='Путь к бинарнику nebula-cert (по умолчанию из PATH или for-all/)')
    
    args = parser.parse_args()
    
    # Определение пути к nebula-cert
    nebula_cert_path = None
    if args.cert_path:
        nebula_cert_path = Path(args.cert_path)
    elif (SCRIPT_DIR / "for-all" / "nebula-cert").exists():
        nebula_cert_path = SCRIPT_DIR / "for-all" / "nebula-cert"
    else:
        nebula_cert_path = shutil.which("nebula-cert")
        if nebula_cert_path:
            nebula_cert_path = Path(nebula_cert_path)
        else:
            print("Ошибка: nebula-cert не найден. Используйте --cert-path или запустите bash setup-binaries.sh", file=sys.stderr)
            sys.exit(1)
    
    # Генерация CA
    if args.generate_ca:
        config = load_config()
        network_name = config.get('net-name', 'nebula-net')
        generate_ca(network_name, nebula_cert_path)
        sys.exit(0)
    
    # Генерация сертификатов для всех узлов
    if args.generate_host_certs:
        config = load_config()
        ca_dir = OUTPUT_DIR / "ca"
        generate_all_host_certs(config, nebula_cert_path, ca_dir, in_pub=in_pub)
        sys.exit(0)
    
    # Основная генерация
    print("Генерация конфигураций Nebula VPN")
    print("=" * 50)
    
    config = load_config()
    print(f"✓ Загружена конфигурация: {config.get('net-name', 'unnamed')}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Проверяем наличие CA-сертификата и генерируем если нет
    ca_dir = OUTPUT_DIR / "ca"
    ca_crt_path = ca_dir / "ca.crt"
    auto_generate = False
    if ca_crt_path.exists():
        print(f"✓ CA-сертификат найден: {ca_crt_path}")
    else:
        print("⚠ CA-сертификат не найден. Генерируем CA...")
        network_name = config.get('net-name', 'nebula-net')
        generate_ca(network_name, nebula_cert_path)
        auto_generate = True
    
    lighthouses = config.get('lighthouse', {})
    hosts = config.get('hosts', {})
    relay_servers = config.get('relay_servers', [])
    ca_pem = config.get('ca_pem', '') or None
    in_pub = config.get('in_pub', '') or None
    
    # Определяем какие узлы генерировать
    if args.only_hosts:
        host_targets = args.host or []
        if not host_targets:
            print("Ошибка: --only-hosts требует указания узлов через --host", file=sys.stderr)
            sys.exit(1)
    else:
        host_targets = args.host if args.host else list(hosts.keys())
    
    # Определяем какие маяки генерировать
    if args.only_lights:
        light_targets = args.light or []
        if not light_targets:
            print("Ошибка: --only-lights требует указания маяков через --light", file=sys.stderr)
            sys.exit(1)
    else:
        light_targets = args.light if args.light else list(lighthouses.keys())
    
    # Фильтрация
    host_targets = [t for t in host_targets if t in hosts]
    light_targets = [l for l in light_targets if l in lighthouses]
    
    if not host_targets and not light_targets:
        print("\nНичего не генерировано - проверьте имена узлов/маяков", file=sys.stderr)
        sys.exit(1)
    
    # Загружаем единый шаблон
    template = load_template()
    
    # Генерация маяков
    if light_targets:
        print(f"\nГенерация маяков ({len(light_targets)} шт.)")
        for lh_name in light_targets:
            lh_data = lighthouses[lh_name]
            rendered = render_config(template, lh_name, lh_data, 'lighthouse', lighthouses, relay_servers, ca_pem)
            write_config(lh_name, rendered, ca_crt_path, generate_cert=auto_generate, in_pub=in_pub)
    
    # Генерация узлов
    if host_targets:
        print(f"\nГенерация узлов ({len(host_targets)} шт.)")
        for host_name in host_targets:
            host_data = hosts[host_name]
            rendered = render_config(template, host_name, host_data, 'host', lighthouses, relay_servers, ca_pem)
            write_config(host_name, rendered, ca_crt_path, generate_cert=auto_generate, in_pub=in_pub)
    
    # Верификация сгенерированных конфигов
    verify_generated_configs(config, lighthouses, hosts, relay_servers)
    
    print("\n" + "=" * 50)
    print(f"Готово! Файлы сохранены в: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
