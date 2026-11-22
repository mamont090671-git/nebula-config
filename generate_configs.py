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

import argparse
import getpass
import ipaddress
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from validators import validate_config_safe

SCRIPT_DIR = Path(__file__).parent
MASTER_CONFIG = SCRIPT_DIR / "config-nebula.yaml"
TEMPLATE = SCRIPT_DIR / "templates/config.yaml"
FOR_ALL_DIR = SCRIPT_DIR / "for-all"
OUTPUT_DIR = SCRIPT_DIR / "output"


def load_config():
    if not MASTER_CONFIG.exists():
        print(f"Ошибка: Конфигурация не найдена: {MASTER_CONFIG}", file=sys.stderr)
        sys.exit(1)

    with open(MASTER_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_template():
    if not TEMPLATE.exists():
        print(f"Ошибка: Шаблон не найден: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        return f.read()


def build_static_host_map_for_client(lighthouses):
    """Строит static_host_map для узла-клиента (список всех маяков с публичными IP:Port)"""
    lines = ["static_host_map:"]
    lines.append("  # Внутренний IPv4 маяка: [Публичный_IP:Порт]")
    lines.append("  # Внутренний IPv6 маяка: [Публичный_IP:Порт]")

    for lh_data in lighthouses.values():
        ipv4_raw = lh_data.get("nebula_ip", {}).get("ipv4", "")
        ipv6_raw = lh_data.get("nebula_ip", {}).get("ipv6", "")
        # P2.2: Автоотсечение маски через ipaddress stdlib
        ipv4 = str(ipaddress.ip_interface(ipv4_raw).ip) if ipv4_raw else ""
        ipv6 = str(ipaddress.ip_interface(ipv6_raw).ip) if ipv6_raw else ""
        public_ip = lh_data.get("public_ip", "")
        port = lh_data.get("port", "")

        if ipv4 and public_ip and port:
            lines.append(f'  "{ipv4}": ["{public_ip}:{port}"]')
        if ipv6 and public_ip and port:
            lines.append(f'  "{ipv6}": ["{public_ip}:{port}"]')

    return "\n".join(lines)


def build_static_host_map_for_lighthouse(lighthouses, current_name):
    """Строит static_host_map для маяка (включая самого себя и другие маяки с публичными IP:Port)"""
    lines = ["static_host_map:"]

    # Добавляем самого себя
    current = lighthouses[current_name]
    ipv4_raw = current.get("nebula_ip", {}).get("ipv4", "")
    ipv6_raw = current.get("nebula_ip", {}).get("ipv6", "")
    public_ip = current.get("public_ip", "")
    port = current.get("port", "")

    if ipv4_raw and public_ip and port:
        ipv4 = str(ipaddress.ip_interface(ipv4_raw).ip)
        lines.append(f'  "{ipv4}": ["{public_ip}:{port}"]')
    if ipv6_raw and public_ip and port:
        ipv6 = str(ipaddress.ip_interface(ipv6_raw).ip)
        lines.append(f'  "{ipv6}": ["{public_ip}:{port}"]')

    # Добавляем другие маяки
    for lh_name, lh_data in lighthouses.items():
        if lh_name != current_name:
            ipv4_raw = lh_data.get("nebula_ip", {}).get("ipv4", "")
            ipv6_raw = lh_data.get("nebula_ip", {}).get("ipv6", "")
            public_ip = lh_data.get("public_ip", "")
            port = lh_data.get("port", "")

            if ipv4_raw and public_ip and port:
                ipv4 = str(ipaddress.ip_interface(ipv4_raw).ip)
                lines.append(f'  "{ipv4}": ["{public_ip}:{port}"]')
            if ipv6_raw and public_ip and port:
                ipv6 = str(ipaddress.ip_interface(ipv6_raw).ip)
                lines.append(f'  "{ipv6}": ["{public_ip}:{port}"]')

    return "\n".join(lines)


def build_lighthouse_hosts_for_client(lighthouses):
    """Строит hosts для узла-клиента (список всех маяков)"""
    lines = []
    for lh_data in lighthouses.values():
        ipv6 = lh_data.get("nebula_ip", {}).get("ipv6", "").split("/")[0]
        ipv4 = lh_data.get("nebula_ip", {}).get("ipv4", "").split("/")[0]
        if ipv6:
            lines.append(f'    - "{ipv6}"')
        if ipv4:
            lines.append(f'    - "{ipv4}"')
    return "\n".join(lines)


def build_lighthouse_hosts_for_lighthouse(lighthouses, current_name):
    """Строит hosts для маяка (только другие маяки)"""
    lines = []
    for lh_name, lh_data in lighthouses.items():
        if lh_name != current_name:
            ipv6 = lh_data.get("nebula_ip", {}).get("ipv6", "").split("/")[0]
            ipv4 = lh_data.get("nebula_ip", {}).get("ipv4", "").split("/")[0]
            if ipv6:
                lines.append(f'    - "{ipv6}"')
            if ipv4:
                lines.append(f'    - "{ipv4}"')
    return "\n".join(lines) if lines else None


def build_relays_servers(relay_servers_list):
    """Строит relay.relays: секцию из списка relay-серверов (4 пробела = как # RELAYS в шаблоне)"""
    if not relay_servers_list:
        return "    # Нет relay-серверов"
    lines = []
    for ip in relay_servers_list:
        lines.append(f'    - "{ip}"')
    return "\n".join(lines)


def build_inline_ca_block(ca_pem):
    """Строит pki.ca секцию с inline PEM"""
    if not ca_pem:
        return None
    lines = ["ca: |"]
    for line in ca_pem.split("\n"):
        lines.append(f"  {line}")
    return "\n".join(lines)


def render_config(
    template,
    node_name,
    node_data,
    node_type,
    lighthouses,
    relay_servers=None,
    ca_pem=None,
    blocklist=None,
    network_dev="nebula1",
    network_subnet="192.168.10.0/24",
    extra_inbound_rules=None,
):
    """Единственная функция рендеринга для любого типа узла"""

    is_lighthouse = node_type == "lighthouse"
    is_relay = is_lighthouse and node_data.get("am_relay", False)

    # Строим секции
    if is_lighthouse:
        static_map = build_static_host_map_for_lighthouse(lighthouses, node_name)
        lh_hosts = build_lighthouse_hosts_for_lighthouse(lighthouses, node_name)
        am_relay_val = str(node_data.get("am_relay", False)).lower()
        am_aware_val = "true"
        use_relays_val = "false" if is_relay else "true"
    else:
        static_map = build_static_host_map_for_client(lighthouses)
        lh_hosts = build_lighthouse_hosts_for_client(lighthouses)
        am_relay_val = "false"
        am_aware_val = "false"
        port_val = str(node_data.get("port", "4242"))
        use_relays_val = "true" if port_val == "0" else "false"

    relays_val = (
        build_relays_servers(relay_servers)
        if not is_relay
        else "    # Нет relay-серверов"
    )
    listen_host = "[::]" if not is_lighthouse else "::"
    listen_port = str(node_data.get("port", "4242"))

    # Inline CA
    inline_ca = build_inline_ca_block(ca_pem)

    # Заменяем плейсхолдеры
    result = template
    result = result.replace("{{HOST_NAME}}", node_name)
    result = result.replace("# STATIC_HOST_MAP", static_map or "# Нет static_host_map")
    result = result.replace("    # LHM", lh_hosts or "    # Нет других маяков")
    result = result.replace("{{AM_RELAY}}", am_relay_val)
    result = result.replace("{{AM_AWARE}}", am_aware_val)
    result = result.replace("{{USE_RELAYS}}", use_relays_val)
    result = result.replace("    # RELAYS", relays_val)
    result = result.replace("{{LISTEN_HOST}}", listen_host)
    result = result.replace("{{LISTEN_PORT}}", listen_port)
    result = result.replace("  # FIREWALL", extra_inbound_rules or "")
    result = result.replace("{{NETWORK_DEV}}", network_dev)
    result = result.replace("{{NETWORK_SUBNET}}", network_subnet)

    # Inline CA замена
    if inline_ca:
        result = result.replace("ca: /etc/nebula/ca.crt", inline_ca)

    # PKI blocklist (отозванные сертификаты)
    if blocklist:
        blocklist_lines = "  blocklist:\n"
        for fp in blocklist:
            blocklist_lines += f'    - "{fp}"\n'
        result = result.replace("  # blocklist:\n", blocklist_lines)
    else:
        result = result.replace("  # blocklist:\n", "  # Нет отозванных сертификатов\n")

    return result


def verify_generated_configs(config, lighthouses, hosts, relay_servers):
    """Проверка сгенерированных конфигов на корректность."""
    errors = []
    warnings = []

    # 1. Проверка relay_servers не пусты для NAT-хостов
    if relay_servers:
        relay_ips = [r for r in relay_servers if r]
        if not relay_ips:
            errors.append(
                "relay_servers пустой — NAT-хосты не будут знать relay-сервер"
            )
    else:
        nat_hosts = [
            name for name, data in hosts.items() if str(data.get("port", "4242")) == "0"
        ]
        if nat_hosts:
            warnings.append(
                f"relay_servers не указан, но есть NAT-хосты с port 0: {', '.join(nat_hosts)}"
            )

    # 2. Проверка port 0 хостов — use_relays: true
    for host_name, host_data in hosts.items():
        port = str(host_data.get("port", "4242"))
        if port == "0":
            config_file = OUTPUT_DIR / host_name / "config.yaml"
            if config_file.exists():
                with open(config_file, "r") as f:
                    content = f.read()
                if "use_relays: true" not in content:
                    errors.append(
                        f"{host_name} (port 0): use_relays: true отсутствует в конфиге"
                    )
                if "relay:" not in content:
                    errors.append(
                        f"{host_name} (port 0): секция relay: отсутствует в конфиге"
                    )
                if "use_relays: false" in content:
                    errors.append(
                        f"{host_name} (port 0): use_relays: false вместо true"
                    )

    # 3. Проверка relay-лайтхауса — am_relay: true, use_relays: false
    for lh_name, lh_data in lighthouses.items():
        if lh_data.get("am_relay", False):
            config_file = OUTPUT_DIR / lh_name / "config.yaml"
            if config_file.exists():
                with open(config_file, "r") as f:
                    content = f.read()
                if "am_relay: true" not in content:
                    errors.append(
                        f"{lh_name} (am_relay): am_relay: true отсутствует в конфиге"
                    )
                if "use_relays: false" not in content:
                    errors.append(
                        f"{lh_name} (am_relay): use_relays: false отсутствует в конфиге"
                    )

    # 4. Проверка static_host_map на клиентах
    for host_name in hosts:
        config_file = OUTPUT_DIR / host_name / "config.yaml"
        if config_file.exists():
            with open(config_file, "r") as f:
                content = f.read()
            if "static_host_map:" not in content:
                errors.append(f"{host_name}: static_host_map отсутствует в конфиге")
            else:
                has_lh_map = False
                for lh_name in lighthouses:
                    lh_ip = (
                        lighthouses[lh_name]
                        .get("nebula_ip", {})
                        .get("ipv4", "")
                        .split("/")[0]
                    )
                    if lh_ip and lh_ip in content:
                        has_lh_map = True
                        break
                if not has_lh_map:
                    warnings.append(
                        f"{host_name}: static_host_map не содержит IPv4 лайтхауса"
                    )

    # 5. Проверка IPv6 hosts на клиентах
    for host_name in hosts:
        config_file = OUTPUT_DIR / host_name / "config.yaml"
        if config_file.exists():
            with open(config_file, "r") as f:
                content = f.read()
            lh_match = content.find("lighthouse:")
            if lh_match != -1:
                hosts_section_start = content.find("hosts:", lh_match)
                if hosts_section_start != -1:
                    hosts_section = content[hosts_section_start + 7 :]
                    hosts_lines = hosts_section.split("\n")[:20]
                    hosts_list = "\n".join(hosts_lines)
                    for lh_name, lh_data in lighthouses.items():
                        ipv6 = (
                            lh_data.get("nebula_ip", {}).get("ipv6", "").split("/")[0]
                        )
                        if ipv6 and ipv6 not in hosts_list:
                            warnings.append(
                                f"{host_name}: hosts секция lighthouse не содержит IPv6 {ipv6} ({lh_name})"
                            )

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
        return

    files_copied = []
    for item in FOR_ALL_DIR.iterdir():
        if item.is_file():
            dest = node_dir / item.name
            shutil.copy2(item, dest)
            files_copied.append(item.name)

    if files_copied:
        print(f"  Скопировано: {', '.join(files_copied)}")


def copy_deploy_script(node_dir):
    """Копирует deploy-скрипт из корня проекта в node_dir"""
    deploy_path = SCRIPT_DIR / "nebula_service.sh"
    if deploy_path.exists():
        shutil.copy2(deploy_path, node_dir / "nebula_service.sh")
        print("  Скопировано: nebula_service.sh (deploy)")
    else:
        print(f"  ⚠️  deploy-скрипт не найден: {deploy_path}", file=sys.stderr)


def copy_ca_to_node(node_dir, ca_crt_path):
    """Копирует CA-сертификат в node_dir"""
    if not ca_crt_path.exists():
        print(f"  Внимание: CA-сертификат не найден: {ca_crt_path}")
        return

    dest = node_dir / "ca.crt"
    shutil.copy2(ca_crt_path, dest)
    print(f"  CA: {dest.name} скопирован")


# Кеш passphrase — спрашиваем один раз за сессию
_passphrase_cache = None


def get_ca_passphrase():
    """Спрашиваем passphrase один раз и кешируем."""
    global _passphrase_cache
    if _passphrase_cache is not None:
        return _passphrase_cache
    _passphrase_cache = getpass.getpass("Введите passphrase для CA-ключа: ")
    return _passphrase_cache


def generate_node_certificate(
    node_name,
    node_data,
    ca_dir,
    nebula_cert_path,
    in_pub=None,
    external_ca_key=None,
    ca_crt_path=None,
):
    """Генерация сертификата для узла/маяка"""
    ipv4 = node_data.get("nebula_ip", {}).get("ipv4", "")
    ipv6 = node_data.get("nebula_ip", {}).get("ipv6", "")

    ip_params = []
    if ipv4:
        ip_params.append(ipv4)
    if ipv6:
        ip_params.append(ipv6)

    if not ip_params:
        print(f"  Ошибка: нет nebula_ip для узла {node_name}", file=sys.stderr)
        return False, None

    ip_string = ",".join(ip_params)
    groups = node_data.get("groups", "home")
    cert_name = node_data.get("name", node_name)

    # P1.1: Если внешний ключ задан — использовать его, иначе из output/
    ca_key = external_ca_key if external_ca_key else ca_dir / "ca.key"
    ca_crt = ca_crt_path if ca_crt_path else ca_dir / "ca.crt"

    node_dir = OUTPUT_DIR / node_name
    node_dir.mkdir(parents=True, exist_ok=True)

    cert_file = node_dir / f"{cert_name}.crt"
    key_file = node_dir / f"{cert_name}.key"

    # Если сертификат уже есть — не перегенерировать (nebula-cert sign ждёт подтверждения)
    if cert_file.exists() and key_file.exists():
        return True, f"{cert_name}.crt"

    cmd = [
        str(nebula_cert_path),
        "sign",
        "-name",
        cert_name,
        "-ip",
        ip_string,
        "-groups",
        groups,
        "-ca-crt",
        str(ca_crt),
        "-ca-key",
        str(ca_key),
        "-out-crt",
        str(node_dir / f"{cert_name}.crt"),
        "-out-key",
        str(node_dir / f"{cert_name}.key"),
    ]

    if in_pub:
        cmd.extend(["-in-pub", in_pub])
        print(f"  Режим key-based signing: -in-pub {in_pub}")

    print(f"  Генерация сертификата для {node_name}...")
    print(f"    Имя: {cert_name}")
    print(f"    IP: {ip_string}")
    print(f"    Группы: {groups}")
    print(f"    Команда: {' '.join(cmd)}")

    # Проверяем ca.key — если зашифрован, спрашиваем passphrase
    env = os.environ.copy()
    with open(ca_key, "r") as kf:
        first_line = kf.readline().strip()
    if "ENCRYPTED" in first_line:
        env["NEBULA_CA_PASSPHRASE"] = get_ca_passphrase()

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True, env=env, timeout=30
        )
        if (node_dir / f"{cert_name}.crt").exists() and (
            node_dir / f"{cert_name}.key"
        ).exists():
            print(f"✓ Сертификат создан: {node_dir / cert_name}.crt")
            print(f"  Ключ: {node_dir / cert_name}.key")
            return True, f"{cert_name}.crt"
        else:
            print("Ошибка: файлы сертификата не созданы", file=sys.stderr)
            return False, None
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации сертификата {node_name}: {e}", file=sys.stderr)
        if e.stderr:
            print(f"  STDERR: {e.stderr}", file=sys.stderr)
        return False, None
    except Exception as e:  # noqa: BLE001
        print(f"Ошибка: {e}", file=sys.stderr)
        return False, None


def write_config(
    node_name,
    config_content,
    ca_crt_path=None,
    generate_cert=True,
    in_pub=None,
    external_ca_key=None,
):
    node_dir = OUTPUT_DIR / node_name
    node_dir.mkdir(parents=True, exist_ok=True)

    output_file = node_dir / "config.yaml"

    if output_file.exists():
        backup = node_dir / f"{node_name}.yaml.backup"
        shutil.copy2(output_file, backup)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(config_content)

    print(f"✓ Создано: {output_file}")

    copy_for_all_files(node_dir)
    copy_deploy_script(node_dir)

    # P1.1: Не копировать ca.crt в output если используется внешний ключ
    if ca_crt_path and not external_ca_key:
        copy_ca_to_node(node_dir, ca_crt_path)

    # Всегда генерируем сертификаты если есть nebula-cert и CA
    if ca_crt_path and ca_crt_path.exists():
        ca_dir = OUTPUT_DIR / "ca"
        config = load_config()
        node_data = config.get("hosts", {}).get(node_name) or config.get(
            "lighthouse", {}
        ).get(node_name)

        if node_data:
            nebula_cert_path = None
            if (SCRIPT_DIR / "nebula-cert").exists():
                nebula_cert_path = SCRIPT_DIR / "nebula-cert"
            else:
                nebula_cert_path = shutil.which("nebula-cert")

            if nebula_cert_path and ca_dir.exists():
                _success, _cert_file = generate_node_certificate(
                    node_name,
                    node_data,
                    ca_dir,
                    nebula_cert_path,
                    in_pub=in_pub,
                    external_ca_key=external_ca_key,
                    ca_crt_path=ca_crt_path,
                )


def generate_ca(network_name, nebula_cert_path):
    """Генерация CA-сертификата"""
    ca_dir = OUTPUT_DIR / "ca"
    ca_dir.mkdir(parents=True, exist_ok=True)

    if not nebula_cert_path.exists():
        print(
            f"Ошибка: nebula-cert не найден по пути {nebula_cert_path}", file=sys.stderr
        )
        sys.exit(1)

    ca_key = ca_dir / "ca.key"
    ca_crt = ca_dir / "ca.crt"

    if ca_key.exists() and ca_crt.exists():
        print(f"CA уже существует в {ca_dir}/")
        return

    cmd = [
        str(nebula_cert_path),
        "ca",
        "-name",
        network_name,
        "-version",
        "2",
        "-out-key",
        str(ca_key),
        "-out-crt",
        str(ca_crt),
    ]

    print(f"Генерация CA для сети '{network_name}'...")
    print(f"  Команда: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if ca_key.exists() and ca_crt.exists():
            print(f"✓ CA создан в: {ca_dir}")
            print(f"  CA ключ: {ca_key}")
            print(f"  CA сертификат: {ca_crt}")
        else:
            print("Ошибка: файлы CA не созданы", file=sys.stderr)
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации CA: {e}", file=sys.stderr)
        if e.stderr:
            print(f"  STDERR: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


def generate_all_host_certs(config, nebula_cert_path, ca_dir, in_pub=None):
    """Генерация сертификатов для всех узлов и маяков"""
    if not ca_dir.exists():
        print(f"Ошибка: CA-сертификат не найден в {ca_dir}", file=sys.stderr)
        print(
            "Сначала сгенерируйте CA: python3 generate_configs.py --generate-ca",
            file=sys.stderr,
        )
        sys.exit(1)

    lighthouses = config.get("lighthouse", {})
    hosts = config.get("hosts", {})

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
        success, _ = generate_node_certificate(
            node_name, node_data, ca_dir, nebula_cert_path, in_pub=in_pub
        )
        if success:
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 50)
    print(f"Итого: {success_count} успешных, {fail_count} ошибок")

    return fail_count == 0


def compute_file_hash(filepath):
    """Вычисляет sha256 хэш файла."""
    import hashlib

    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_remote_file_hash(ssh_target, remote_path):
    """Вычисляет sha256 хэш файла на удалённом сервере через md5sum/sha256sum."""
    cmd = f'scp -q "{ssh_target}:{remote_path}" /dev/stdout | sha256sum'
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return result.stdout.split()[0]
    return None


def detect_remote_arch(ssh_target):
    """Определяет архитекцию удалённой машины через SSH."""
    cmd = f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "{ssh_target}" "uname -m"'
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    arch = result.stdout.strip()
    if arch == "x86_64":
        return "amd64"
    elif arch in ("i386", "i686"):
        return "386"
    elif arch in ("aarch64", "arm64"):
        return "arm64"
    elif arch == "armv5l":
        return "arm-5"
    elif arch == "armv6l":
        return "arm-6"
    elif arch in ("armv7l", "armhf"):
        return "arm-7"
    elif arch == "riscv64":
        return "riscv64"
    elif arch == "loongarch64":
        return "loong64"
    elif arch in ("mips", "mipsb"):
        return "mips"
    elif arch in ("mipsel", "mipsle"):
        return "mipsle"
    elif arch in ("mips64", "mips64b"):
        return "mips64"
    elif arch in ("mips64el", "mips64le"):
        return "mips64le"
    elif arch in ("ppc64le", "ppc64"):
        return "ppc64le"
    return None


def get_latest_release():
    """Получает последний релиз Nebula."""
    # Пробуем gh → curl
    for cmd in [
        "gh release list --repo slackhq/nebula --limit 1 --json tagName --jq .[0].tagName 2>/dev/null",
        "curl -sL https://api.github.com/repos/slackhq/nebula/releases/latest",
    ]:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15, check=False
        )
        if r.returncode == 0:
            import re

            m = re.search(r'"tag_name":\s*"\K[^"]+', r.stdout)
            if m:
                return m.group(0)
            # gh output
            lines = r.stdout.strip().split("\n")
            if lines and "v" in lines[0]:
                return lines[0].strip()
    return None


def deploy_binaries(ssh_target, remote_path):
    """Автоопределяет архитекцию, скачивает и устанавливает бинарники Nebula."""
    arch = detect_remote_arch(ssh_target)
    if not arch:
        return False, "Не удалось определить архитекцию"

    version = get_latest_release()
    if not version:
        return False, "Не удалось получить версию релиза"

    # Проверяем есть ли бинарники
    check_cmd = f'ssh "{ssh_target}" "test -f {remote_path}/nebula && test -f {remote_path}/nebula-cert"'
    r = subprocess.run(
        check_cmd, shell=True, capture_output=True, text=True, check=False
    )
    if r.returncode == 0:
        # Проверяем версию
        ver_cmd = f'ssh "{ssh_target}" "{remote_path}/nebula-cert version 2>&1 || {remote_path}/nebula version 2>&1 || echo unknown"'
        vr = subprocess.run(
            ver_cmd, shell=True, capture_output=True, text=True, check=False
        )
        current = vr.stdout.strip().split()[0] if vr.stdout.strip() else "unknown"
        if current == version:
            return True, f"Небуда {current} уже установлена"

    # Скачиваем и устанавливаем
    archive = f"nebula-{version}-linux-{arch}.tar.gz"
    url = f"https://github.com/slackhq/nebula/releases/download/{version}/{archive}"

    install_cmd = f"""ssh "{ssh_target}" <<'SCRIPT'
set -e
mkdir -p {remote_path}
curl -fSL --retry 3 {url} -o /tmp/{archive}
tar xzf /tmp/{archive} -C /tmp
for bin in nebula nebula-cert; do
    src=$(find /tmp -name "$bin" -type f ! -name "*_test" 2>/dev/null | head -1)
    if [ -n "$src" ]; then
        cp -v "$src" {remote_path}/"$bin"
        chmod +x {remote_path}/"$bin"
    fi
done
rm -rf /tmp/{archive} /tmp/nebula-*
SCRIPT"""
    r = subprocess.run(
        install_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if r.returncode != 0:
        return False, f"Установка бинарников FAILED: {r.stderr[:300]}"
    return True, f"Установлено {version}"


def deploy_service(ssh_target, remote_path):
    """Создаёт и включает systemd-сервис Nebula."""
    service_content = f"""[Unit]
Description=Nebula overlay networking
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
ExecStart={remote_path}/nebula -config {remote_path}/config.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

# Hardening
User=root
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE
ProtectSystem=strict
ProtectHome=true
NoNewPrivileges=true
ReadWritePaths={remote_path}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""

    cmd = f"""ssh "{ssh_target}" <<'SCRIPT'
cat > /etc/systemd/system/nebula.service << 'EOF'
{service_content}
EOF
systemctl daemon-reload
systemctl enable nebula
SCRIPT"""
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=30, check=False
    )
    if r.returncode != 0:
        return False, f"Создание сервиса FAILED: {r.stderr[:300]}"
    return True, "Сервис создан и включён"


def deploy_configs(config, lighthouses, hosts, dry_run=False):
    """Деплой конфигов на удалённые сервера через ssh_target с хэш-фильтрацией.

    Алгоритм:
    1. Генерация -> локальный подсчёт хэшей -> фильтрация изменённых
    2. SCP только для изменённых файлов
    3. Селективный restart nebula только для изменившихся хостов
    """
    all_nodes = {}
    for name, data in lighthouses.items():
        all_nodes[name] = data
    for name, data in hosts.items():
        all_nodes[name] = data

    deployed = 0
    skipped = 0
    failed = 0
    would_change = 0
    would_skip = 0

    if dry_run:
        print("\n" + "=" * 60)
        print("РЕЖИМ ПРЕДПРОСМОТРА (dry-run) — ничего не изменится")
        print("=" * 60)

    for node_name, node_data in all_nodes.items():
        ssh_target = node_data.get("ssh_target")
        if not ssh_target:
            print(f"  ⊘ {node_name}: нет ssh_target, пропускаю")
            continue

        # Парсим user@host:/path
        parts = ssh_target.split(":")
        if len(parts) != 2:
            print(f"  ✗ {node_name}: неверный формат ssh_target: {ssh_target}")
            failed += 1
            continue

        remote_host, remote_base = parts

        node_dir = OUTPUT_DIR / node_name
        if not node_dir.exists():
            print(f"  ✗ {node_name}: выходная папка не найдена")
            failed += 1
            continue

        all_files = [item for item in node_dir.iterdir() if item.is_file()]

        # Проверяем хэши на сервере
        needs_deploy = False
        changed_files = []
        for item in all_files:
            remote_path = f"{remote_base}/{item.name}"
            local_hash = compute_file_hash(item)
            remote_hash = compute_remote_file_hash(ssh_target, remote_path)
            if remote_hash is None:
                # Файл не существует на сервере — нужно копировать
                needs_deploy = True
                changed_files.append(f"[НОВЫЙ] {item.name}")
                break
            if local_hash != remote_hash:
                needs_deploy = True
                changed_files.append(f"[ИЗМЕНЁН] {item.name}")
                break

        if not needs_deploy:
            print(f"  = {node_name}: всё unchanged, пропускаю")
            skipped += 1
            if dry_run:
                would_skip += 1
            continue

        if dry_run:
            would_change += 1
            print(f"\n  📋 {node_name} ({remote_host}):")
            print(f"     Файлы для деплоя: {', '.join(changed_files)}")
            print("     Статус бинарников: [проверка через SSH]")
            print("     systemd-сервис: [создание/обновление]")
            print(
                f"     Файлы: {' → '.join(f'{f.name} → {remote_base}/{f.name}' for f in all_files)}"
            )
            print("     Перезапуск nebula: ДА")
            continue

        # Деплоим бинарники (автоопределение архитектуры + скачивание)
        binaries_result = deploy_binaries(ssh_target, remote_base)
        if not binaries_result[0]:
            print(f"  ✗ {node_name}: бинарники FAILED: {binaries_result[1]}")
            failed += 1
            continue
        else:
            print(f"  📦 {node_name}: {binaries_result[1]}")

        # Создаём systemd сервис
        service_result = deploy_service(ssh_target, remote_base)
        if not service_result[0]:
            print(f"  ✗ {node_name}: сервис FAILED: {service_result[1]}")
            failed += 1
            continue
        else:
            print(f"  ⚙️  {node_name}: {service_result[1]}")

        # Деплоим конфиги
        files_copied = []
        for item in all_files:
            remote_path = f"{remote_base}/{item.name}"
            cmd = f'scp "{item}" "{ssh_target}:{remote_path}"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                files_copied.append(item.name)
                print(f"  ✓ {node_name}: {item.name} → {remote_host}")
            else:
                print(f"  ✗ {node_name}: scp {item.name} → {remote_host} FAILED")

        # Перезапускаем nebula
        if True:  # перезапуск всегда после деплоя
            ssh_cmd = f'ssh "{remote_host}" "systemctl restart nebula && systemctl status nebula --no-pager | head -15"'
            result = subprocess.run(
                ssh_cmd, shell=True, capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                print(f"  ↻ {node_name}: nebula перезапущен на {remote_host}")
                # Выводим статус сервиса
                for line in result.stdout.strip().split("\n")[-5:]:
                    print(f"      {line}")
                deployed += 1
            else:
                print(
                    f"  ✗ {node_name}: перезапуск nebula на {remote_host} FAILED: {result.stderr[:200]}"
                )
                failed += 1
        else:
            print(f"  ✗ {node_name}: нет файлов скопировано")
            failed += 1

    if dry_run:
        print(f"\n{'=' * 60}")
        print("ИТОГО ПРЕДПРОСМОТРА:")
        print(f"  📋 Будет изменено: {would_change} узел(ов)")
        print(f"  = Будет пропущено (unchanged): {would_skip} узел(ов)")
        print(f"  ✗ Ошибок: {failed} узел(ов)")
        if would_change:
            print("\n  Запустите без --dry-run для фактического деплоя.")
        print(f"{'=' * 60}")
    else:
        if skipped:
            print(f"\n  Пропущено unchanged: {skipped}")
        if failed:
            print(f"\n  Ошибок: {failed}")
        print(f"  Развернуто: {deployed}")

    return deployed


def main():
    parser = argparse.ArgumentParser(
        description="Генератор конфигураций Nebula VPN",
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
        """,
    )

    parser.add_argument(
        "--host",
        nargs="+",
        metavar="HOST",
        help="Имена узлов для генерации (по умолчанию все)",
    )
    parser.add_argument(
        "--light",
        nargs="+",
        metavar="LIGHT",
        help="Имена маяков для генерации (по умолчанию все)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Явная генерация всех узлов и всех маяков (по умолчанию)",
    )
    parser.add_argument(
        "--only-hosts",
        action="store_true",
        help="Генерировать только узлы (без маяков)",
    )
    parser.add_argument(
        "--only-lights",
        action="store_true",
        help="Генерировать только маяки (без узлов)",
    )
    parser.add_argument(
        "--generate-ca", action="store_true", help="Сгенерировать CA-сертификат"
    )
    parser.add_argument(
        "--generate-host-certs",
        action="store_true",
        help="Сгенерировать сертификаты для всех узлов",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Развернуть сгенерированные конфиги на удалённые сервера через ssh_target",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Предпросмотр --push: показать что изменится без деплоя",
    )
    parser.add_argument(
        "--check-certs",
        action="store_true",
        help="Проверить срок действия всех сертификатов в output/ (exit 1 если < 30 дней)",
    )
    parser.add_argument(
        "--renew-expiring",
        action="store_true",
        help="Перевыпустить сертификаты для узлов с истекающими < 30 дней",
    )
    parser.add_argument(
        "--cert-path",
        type=str,
        default=None,
        help="Путь к бинарнику nebula-cert (по умолчанию из PATH или for-all/)",
    )

    args = parser.parse_args()

    # Определение пути к nebula-cert
    nebula_cert_path = None
    if args.cert_path:
        nebula_cert_path = Path(args.cert_path)
    elif (SCRIPT_DIR / "nebula-cert").exists():
        nebula_cert_path = SCRIPT_DIR / "nebula-cert"
    else:
        nebula_cert_path = shutil.which("nebula-cert")
        if nebula_cert_path:
            nebula_cert_path = Path(nebula_cert_path)
        else:
            print(
                "Ошибка: nebula-cert не найден. Установите --cert-path или положите nebula-cert в корень проекта.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Генерация CA
    if args.generate_ca:
        config = load_config()
        network_name = config.get("net-name", "nebula-net")
        generate_ca(network_name, nebula_cert_path)
        sys.exit(0)

    # Загрузка конфига и in_pub
    config = load_config()
    in_pub = config.get("in_pub", "") or None

    # Генерация сертификатов для всех узлов
    if args.generate_host_certs:
        ca_dir = OUTPUT_DIR / "ca"
        generate_all_host_certs(config, nebula_cert_path, ca_dir, in_pub=in_pub)
        sys.exit(0)

    # Загрузка конфига и базовых переменных (до --check-certs для --renew-expiring)
    config = load_config()
    print(f"✓ Загружена конфигурация: {config.get('net-name', 'unnamed')}")

    lighthouses = config.get("lighthouse", {})
    hosts = config.get("hosts", {})
    relay_servers = config.get("relay_servers", [])
    ca_pem = config.get("ca_pem", "") or None
    in_pub = config.get("in_pub", "") or None
    ca_key_path = config.get("ca_key_path", "") or None
    blocklist = config.get("blocklist", []) or None
    network_dev = config.get("dev", "nebula1")

    # Выводим subnet из первого узла
    import ipaddress

    all_nodes = {**config.get("lighthouse", {}), **config.get("hosts", {})}
    network_subnet = "192.168.10.0/24"  # fallback
    for name, data in all_nodes.items():
        nebula_ip = data.get("nebula_ip", {}).get("ipv4", "")
        if nebula_ip:
            network_subnet = str(ipaddress.ip_network(nebula_ip, strict=False))
            break

    # P1.1: Если ca_key_path задан — используем внешний ключ
    external_ca_key = None
    if ca_key_path:
        external_ca_key = Path(ca_key_path)
        if not external_ca_key.exists():
            print(
                f"⚠ ca_key_path задан, но файл не найден: {external_ca_key}",
                file=sys.stderr,
            )
            external_ca_key = None
        else:
            print(f"✓ Используем внешний CA-ключ: {external_ca_key}")
            print(
                f"  CA не будет сгенерирован — используется ключ из {external_ca_key}"
            )

    # Определяем какие узлы генерировать
    if args.only_hosts:
        host_targets = args.host or []
        if not host_targets:
            print(
                "Ошибка: --only-hosts требует указания узлов через --host",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        host_targets = args.host if args.host else list(hosts.keys())

    # Определяем какие маяки генерировать
    if args.only_lights:
        light_targets = args.light or []
        if not light_targets:
            print(
                "Ошибка: --only-lights требует указания маяков через --light",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        light_targets = args.light if args.light else list(lighthouses.keys())

    # Фильтрация
    host_targets = [t for t in host_targets if t in hosts]
    light_targets = [l for l in light_targets if l in lighthouses]

    if not host_targets and not light_targets:
        print(
            "\nНичего не генерировано - проверьте имена узлов/маяков", file=sys.stderr
        )
        sys.exit(1)

    # Загружаем единый шаблон
    template = load_template()

    # CA
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ca_dir = OUTPUT_DIR / "ca"
    ca_crt_path = ca_dir / "ca.crt"
    auto_generate = False
    if ca_crt_path.exists():
        print(f"✓ CA-сертификат найден: {ca_crt_path}")
    else:
        print("⚠ CA-сертификат не найден. Генерируем CA...")
        network_name = config.get("net-name", "nebula-net")
        generate_ca(network_name, nebula_cert_path)
        auto_generate = True

    # P2.1: Валидация конфига
    is_valid, error = validate_config_safe(config)
    if not is_valid:
        print(f"❌ Ошибка валидации конфига: {error}", file=sys.stderr)
        sys.exit(1)
    else:
        print("✓ Конфиг валиден")

    # Проверка сертификатов
    if args.check_certs:
        import datetime
        import json

        output_dir = OUTPUT_DIR
        if not output_dir.exists():
            print("Ошибка: output/ не существует. Сначала сгенерируйте конфиги.")
            sys.exit(1)

        crt_files = list(output_dir.glob("**/*.crt"))
        if not crt_files:
            print("Нет .crt файлов в output/")
            sys.exit(0)

        now = datetime.datetime.now(datetime.timezone.utc)
        expired = []
        expiring_soon = []
        valid = []

        for crt_file in sorted(crt_files):
            if crt_file.parent.name == "ca":
                continue

            try:
                cert_cmd = str(nebula_cert_path) if nebula_cert_path else "nebula-cert"
                result = subprocess.run(
                    [cert_cmd, "print", "-path", str(crt_file)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    expired.append((crt_file.name, "ошибка чтения"))
                    continue

                # Парсим JSON-вывод nebula-cert print
                data = json.loads(result.stdout)
                not_after = data["details"]["notAfter"]
                expiry = datetime.datetime.fromisoformat(not_after)
                # Приводим к UTC для сравнения
                if expiry.tzinfo is not None:
                    expiry = expiry.astimezone(datetime.timezone.utc)

                days_left = (expiry - now).days

                if expiry < now:
                    expired.append((crt_file.name, f"{days_left} дн."))
                elif days_left <= 30:
                    expiring_soon.append(
                        (crt_file.name, f"{days_left} дн. ({expiry.date()})")
                    )
                else:
                    valid.append((crt_file.name, f"{days_left} дн."))
            except subprocess.TimeoutExpired:
                expired.append((crt_file.name, "таймаут"))
            except json.JSONDecodeError as e:
                expired.append((crt_file.name, f"JSON parse error: {e}"))
            except KeyError as e:
                expired.append((crt_file.name, f"missing field: {e}"))
            except ValueError as e:
                expired.append((crt_file.name, f"date parse error: {e}"))
            except Exception as e:  # noqa: BLE001
                expired.append((crt_file.name, str(e)))

        # Таблица
        print("\n=== Аудит сертификатов ===")
        print(f"{'Файл':<25} {'Статус':<15} {'Осталось':<20}")
        print("-" * 60)

        if valid:
            print(f"\n✅ Валидные ({len(valid)}):")
            for name, days in valid:
                print(f"  {name:<23} {'OK':<13} {days}")

        if expiring_soon:
            print(f"\n⚠ Истекают в течение 30 дней ({len(expiring_soon)}):")
            for name, days in expiring_soon:
                print(f"  {name:<23} {'WARNING':<13} {days}")

        if expired:
            print(f"\n❌ Просроченные ({len(expired)}):")
            for name, days in expired:
                print(f"  {name:<23} {'EXPIRED':<13} {days}")

        if expiring_soon or expired:
            print(
                f"\n⚠ ИТОГО: {len(expiring_soon)} истекающих, {len(expired)} просроченных"
            )
            # Если --renew-expiring — перевыпускаем вместо выхода
            if args.renew_expiring:
                renew_count = 0
                for name, days in expiring_soon + expired:
                    # Ищем файл в output/
                    for crt_file in sorted(output_dir.glob("**/*.crt")):
                        if crt_file.parent.name == "ca":
                            continue
                        if name in crt_file.name:
                            # Удаляем старый сертификат и ключ
                            node_dir = crt_file.parent
                            cert_base = crt_file.stem
                            old_crt = crt_file
                            old_key = node_dir / f"{cert_base}.key"
                            old_crt.unlink()
                            if old_key.exists():
                                old_key.unlink()
                            print(f"\n  🔄 Перевыпуск: {name} ({days})")

                            # Перезапускаем генерацию нового сертификата
                            all_nodes = {}
                            for lh_name, lh_data in lighthouses.items():
                                all_nodes[lh_name] = lh_data
                            for host_name, host_data in hosts.items():
                                all_nodes[host_name] = host_data

                            if name not in all_nodes:
                                print(
                                    f"    ✗ Узел '{name}' не найден в конфиге — пропускаю"
                                )
                                continue

                            node_data = all_nodes[name]
                            ca_dir_renew = OUTPUT_DIR / "ca"
                            in_pub_val = config.get("in_pub", "") or None

                            success, _ = generate_node_certificate(
                                name,
                                node_data,
                                ca_dir_renew,
                                nebula_cert_path,
                                in_pub=in_pub_val,
                                external_ca_key=external_ca_key,
                                ca_crt_path=ca_crt_path,
                            )
                            if success:
                                print(f"    ✓ Перевыпущен: {node_dir / cert_base}.crt")
                                renew_count += 1
                            else:
                                print("    ✗ Ошибка перевыпуска")
                if renew_count:
                    print(f"\n✅ Перевыпущено: {renew_count} сертификат(ов)")
                    # Перезаписываем конфиги для обновлённых узлов
                    print("\n  🔄 Перезапись конфигов...")
                    for lh_name in light_targets:
                        lh_data = lighthouses[lh_name]
                        rendered = render_config(
                            template,
                            lh_name,
                            lh_data,
                            "lighthouse",
                            lighthouses,
                            relay_servers,
                            ca_pem,
                            blocklist,
                            network_dev=network_dev,
                            network_subnet=network_subnet,
                        )
                        write_config(lh_name, rendered, ca_crt_path, False, in_pub)
                    for host_name in host_targets:
                        host_data = hosts[host_name]
                        rendered = render_config(
                            template,
                            host_name,
                            host_data,
                            "host",
                            lighthouses,
                            relay_servers,
                            ca_pem,
                            blocklist,
                            network_dev=network_dev,
                            network_subnet=network_subnet,
                        )
                        write_config(host_name, rendered, ca_crt_path, False, in_pub)
                    print("  ✓ Конфиги обновлены")
                else:
                    print(
                        "\n  ⚠ Не удалось перевыпустить ни один сертификат — проверьте доступность nebula-cert и CA"
                    )
                    sys.exit(1)
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            print(f"\n✅ ВСЕ сертификаты валидны ({len(valid)} шт.)")
            sys.exit(0)

    # Основная генерация
    print("Генерация конфигураций Nebula VPN")
    print("=" * 50)

    # Генерация маяков
    if light_targets:
        print(f"\nГенерация маяков ({len(light_targets)} шт.)")
        for lh_name in light_targets:
            lh_data = lighthouses[lh_name]
            rendered = render_config(
                template,
                lh_name,
                lh_data,
                "lighthouse",
                lighthouses,
                relay_servers,
                ca_pem,
                blocklist,
                network_dev=network_dev,
                network_subnet=network_subnet,
            )
            write_config(
                lh_name,
                rendered,
                ca_crt_path,
                generate_cert=auto_generate,
                in_pub=in_pub,
            )

    # Генерация узлов
    if host_targets:
        print(f"\nГенерация узлов ({len(host_targets)} шт.)")
        for host_name in host_targets:
            host_data = hosts[host_name]
            rendered = render_config(
                template,
                host_name,
                host_data,
                "host",
                lighthouses,
                relay_servers,
                ca_pem,
                blocklist,
                network_dev=network_dev,
                network_subnet=network_subnet,
            )
            write_config(
                host_name,
                rendered,
                ca_crt_path,
                generate_cert=auto_generate,
                in_pub=in_pub,
            )

    # Верификация сгенерированных конфигов
    verify_generated_configs(config, lighthouses, hosts, relay_servers)

    # P3.1: Деплой через ssh_target
    if args.push:
        deployed = deploy_configs(config, lighthouses, hosts, dry_run=args.dry_run)
        if deployed:
            print(f"\n✓ Развернуто на {deployed} узлах")
        else:
            print("\n⚠ Деплой пропущен (нет ssh_target или ошибка)")

    print("\n" + "=" * 50)
    print(f"Готово! Файлы сохранены в: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
