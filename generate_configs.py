#!/usr/bin/env python3
"""
Генератор конфигураций Nebula VPN
Читает config-nebula.yaml и создаёт конфигурационные файлы для узлов и маяков

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
HOST_TEMPLATE = SCRIPT_DIR / "host/config.yaml"
LIGHTHOUSE_TEMPLATE = SCRIPT_DIR / "lighthouse/config.yaml"
FOR_ALL_DIR = SCRIPT_DIR / "for-all"
OUTPUT_DIR = SCRIPT_DIR / "output"


def load_config():
    if not MASTER_CONFIG.exists():
        print(f"Ошибка: Конфигурация не найдена: {MASTER_CONFIG}", file=sys.stderr)
        sys.exit(1)
    
    with open(MASTER_CONFIG, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_template(name):
    if name == "host":
        path = HOST_TEMPLATE
    elif name == "lighthouse":
        path = LIGHTHOUSE_TEMPLATE
    else:
        raise ValueError(f"Неизвестный шаблон: {name}")
    
    if not path.exists():
        print(f"Ошибка: Шаблон не найден: {path}", file=sys.stderr)
        sys.exit(1)
    
    with open(path, 'r', encoding='utf-8') as f:
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


def render_host_config(template, host_name, host_data, lighthouses):
    lines = template.split('\n')
    result = []
    
    static_map = build_static_host_map_for_client(lighthouses)
    lh_hosts = build_lighthouse_hosts_for_client(lighthouses)
    listen_port = str(host_data.get('port', '0'))
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.strip() == 'static_host_map:':
            i += 1
            while i < len(lines) and (lines[i].strip().startswith('#') or 
                                       lines[i].strip().startswith('"') or 
                                       lines[i].strip() == ''):
                i += 1
            result.extend(static_map.split('\n'))
            continue
        
        if 'GPD_win_4.crt' in line:
            result.append(line.replace('GPD_win_4.crt', f'{host_name}.crt'))
            i += 1
            continue
        if 'GPD_win_4.key' in line:
            result.append(line.replace('GPD_win_4.key', f'{host_name}.key'))
            i += 1
            continue
        
        if line.strip().startswith('port:') and 'listen' in '\n'.join(lines[max(0,i-3):i]):
            result.append(f'  port: {listen_port}')
            i += 1
            continue
        
        if line.strip() == 'use_relays: true' and 'relay:' in '\n'.join(lines[max(0,i-3):i]):
            result.append('  use_relays: true')
            i += 1
            continue
        
        if line.strip() == 'hosts:':
            i += 1
            while i < len(lines) and (lines[i].strip().startswith('#') or 
                                      lines[i].strip().startswith('-') or
                                      lines[i].strip() == ''):
                i += 1
            result.append(line)
            result.extend(lh_hosts.split('\n'))
            continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)


def render_lighthouse_config(template, lh_name, lh_data, lighthouses):
    lines = template.split('\n')
    result = []
    
    static_map = build_static_host_map_for_lighthouse(lighthouses, lh_name)
    other_lh_hosts = build_lighthouse_hosts_for_lighthouse(lighthouses, lh_name)
    port = str(lh_data.get('port', '4242'))
    
    is_single_lighthouse = len(lighthouses) == 1
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.strip() == 'static_host_map:':
            i += 1
            while i < len(lines) and (lines[i].strip().startswith('#') or 
                                       lines[i].strip().startswith('"') or 
                                       lines[i].strip() == ''):
                i += 1
            if static_map and not is_single_lighthouse:
                result.extend(static_map.split('\n'))
            continue
        
        if 'lighthouse.crt' in line:
            result.append(line.replace('lighthouse.crt', f'{lh_name}.crt'))
            i += 1
            continue
        if 'lighthouse.key' in line:
            result.append(line.replace('lighthouse.key', f'{lh_name}.key'))
            i += 1
            continue
        
        if line.strip() == 'port: 4242':
            result.append(f'  port: {port}')
            i += 1
            continue
        
        if line.strip() == 'hosts:':
            i += 1
            while i < len(lines) and (lines[i].strip().startswith('#') or 
                                      lines[i].strip().startswith('-') or
                                      lines[i].strip() == ''):
                i += 1
            if other_lh_hosts and not is_single_lighthouse:
                result.append(line)
                result.extend(other_lh_hosts.split('\n'))
            continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)


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


def generate_node_certificate(node_name, node_data, ca_dir, nebula_cert_path):
    """Генерация сертификата для узла/маяка"""
    # Собираем IPv4/IPv6 для -ip параметра
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
    
    # Группы
    groups = node_data.get('groups', 'home')
    
    # Имя узла для сертификата
    cert_name = node_data.get('name', node_name)
    
    # Создаём сертификаты сразу в папке узла
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


def write_config(node_name, config_content, ca_crt_path=None, generate_cert=True):
    node_dir = OUTPUT_DIR / node_name
    node_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = node_dir / "config.yaml"
    
    if output_file.exists():
        backup = node_dir / f"{node_name}.yaml.backup"
        shutil.copy2(output_file, backup)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"✓ Создано: {output_file}")
    
    # Копировать файлы из for-all/
    copy_for_all_files(node_dir)
    
    # Копировать CA-сертификат если есть
    if ca_crt_path:
        copy_ca_to_node(node_dir, ca_crt_path)
    
    # Генерировать сертификат если есть CA и разрешено
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
                    node_name, node_data, ca_dir, nebula_cert_path
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


def generate_all_host_certs(config, nebula_cert_path, ca_dir):
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
        success, _ = generate_node_certificate(node_name, node_data, ca_dir, nebula_cert_path)
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
  
  # Явная генерация всех узлов и маяков
  python3 generate_configs.py --all
  
  # Только указанные узлы + все маяки
  python3 generate_configs.py --host NL-HostVDS RU
  
  # Все узлы + указанные маяки
  python3 generate_configs.py --light light-1
  
  # Только узлы NL-HostVDS и RU (без маяков)
  python3 generate_configs.py --only-hosts --host NL-HostVDS RU
  
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
            print("Ошибка: nebula-cert не найден. Используйте --cert-path для указания пути", file=sys.stderr)
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
        generate_all_host_certs(config, nebula_cert_path, ca_dir)
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
    if ca_crt_path.exists():
        print(f"✓ CA-сертификат найден: {ca_crt_path}")
    else:
        print("⚠ CA-сертификат не найден. Генерируем CA...")
        network_name = config.get('net-name', 'nebula-net')
        generate_ca(network_name, nebula_cert_path)
        auto_generate = True
    
    lighthouses = config.get('lighthouse', {})
    hosts = config.get('hosts', {})
    
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
    
    # Генерация маяков
    if light_targets:
        print(f"\nГенерация маяков ({len(light_targets)} шт.)")
        template = load_template("lighthouse")
        for lh_name in light_targets:
            lh_data = lighthouses[lh_name]
            rendered = render_lighthouse_config(template, lh_name, lh_data, lighthouses)
            write_config(lh_name, rendered, ca_crt_path, generate_cert=auto_generate)
    
    # Генерация узлов
    if host_targets:
        print(f"\nГенерация узлов ({len(host_targets)} шт.)")
        template = load_template("host")
        for host_name in host_targets:
            host_data = hosts[host_name]
            rendered = render_host_config(template, host_name, host_data, lighthouses)
            write_config(host_name, rendered, ca_crt_path, generate_cert=auto_generate)
    
    print("\n" + "=" * 50)
    print(f"Готово! Файлы сохранены в: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
