#!/usr/bin/env python3
"""
Валидатор config-nebula.yaml. Без pydantic — только stdlib.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network, IPv4Address
import re


def _validate_fingerprint(fp: str) -> bool:
    """Проверяет формат отпечатка SHA-256: sha256:<64 hex chars>"""
    pattern = r'^sha256:[0-9a-fA-F]{64}$'
    return bool(re.match(pattern, fp))


@dataclass
class NebulaIP:
    """Внутренний IP узла."""
    ipv4: str | None = None
    ipv6: str | None = None

    def __post_init__(self):
        if self.ipv4:
            try:
                IPv4Network(self.ipv4, strict=False)
            except ValueError:
                raise ValueError(f"Невалидный IPv4 CIDR: {self.ipv4}. Формат: 192.168.10.10/24")
        if self.ipv6:
            try:
                IPv6Network(self.ipv6, strict=False)
            except ValueError:
                raise ValueError(f"Невалидный IPv6 CIDR: {self.ipv6}. Формат: fd00:1234:5678:a::101/64")


@dataclass
class HostConfig:
    """Конфигурация узла."""
    groups: str
    nebula_ip: NebulaIP
    port: str = "4242"
    public_ip: str | None = None
    name: str | None = None

    def __post_init__(self):
        try:
            p = int(self.port)
        except ValueError:
            raise ValueError(f"Порт должен быть числом: {self.port}")
        if p < 0 or p > 65535:
            raise ValueError(f"Порт должен быть 0-65535, получено: {p}")
        if self.public_ip:
            try:
                IPv4Address(self.public_ip)
            except ValueError:
                raise ValueError(f"Невалидный публичный IP: {self.public_ip}. Формат: 1.2.3.4")


@dataclass
class LighthouseConfig:
    """Конфигурация маяка."""
    groups: str
    nebula_ip: NebulaIP
    port: str
    public_ip: str | None = None
    am_relay: bool = False

    def __post_init__(self):
        try:
            p = int(self.port)
        except ValueError:
            raise ValueError(f"Порт должен быть числом: {self.port}")
        if p < 0 or p > 65535:
            raise ValueError(f"Порт должен быть 0-65535, получено: {p}")
        if self.public_ip:
            try:
                IPv4Address(self.public_ip)
            except ValueError:
                raise ValueError(f"Невалидный публичный IP: {self.public_ip}. Формат: 1.2.3.4")
        if self.am_relay and not self.public_ip:
            raise ValueError("am_relay: true требует public_ip")


@dataclass
class NebulaConfig:
    """Мастер-конфигурация Nebula."""
    net_name: str
    relay_servers: list = field(default_factory=list)
    ca_pem: str = ""
    in_pub: str = ""
    ca_key_path: str = ""
    blocklist: list = field(default_factory=list)
    lighthouse: dict = field(default_factory=dict)
    hosts: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.net_name.strip():
            raise ValueError("net-name не может быть пустым")
        self.ca_pem = self.ca_pem.strip() if self.ca_pem else ""
        self.in_pub = self.in_pub.strip() if self.in_pub else ""
        self.ca_key_path = self.ca_key_path.strip() if self.ca_key_path else ""
        # nebula_ip обязателен
        for label, nodes in [('lighthouse', self.lighthouse), ('host', self.hosts)]:
            for name, data in nodes.items():
                if isinstance(data, dict):
                    nip = data.get('nebula_ip', {})
                    if not nip.get('ipv4') and not nip.get('ipv6'):
                        raise ValueError(f"{label} '{name}': обязано иметь nebula_ip.ipv4 или nebula_ip.ipv6")
        # дубликаты relay
        seen = set()
        for ip in self.relay_servers:
            if ip in seen:
                raise ValueError(f"Дублирующийся relay_server: {ip}")
            seen.add(ip)
        # валидация blocklist (SHA-256 отпечатки)
        for fp in self.blocklist:
            if not _validate_fingerprint(fp):
                raise ValueError(f"Невалидный отпечаток в blocklist: {fp}. Формат: sha256:<64 hex chars>")


def validate_config(config_dict: dict) -> NebulaConfig:
    """Валидирует конфиг и возвращает NebulaConfig."""
    # Валидируем lighthouse
    for lh_name, lh_data in config_dict.get('lighthouse', {}).items():
        if isinstance(lh_data, dict):
            lighthouse = LighthouseConfig(
                groups=lh_data.get('groups', ''),
                nebula_ip=NebulaIP(
                    ipv4=lh_data.get('nebula_ip', {}).get('ipv4'),
                    ipv6=lh_data.get('nebula_ip', {}).get('ipv6')
                ),
                port=lh_data.get('port', '4242'),
                public_ip=lh_data.get('public_ip'),
                am_relay=lh_data.get('am_relay', False)
            )
    
    # Валидируем hosts
    for host_name, host_data in config_dict.get('hosts', {}).items():
        if isinstance(host_data, dict):
            host = HostConfig(
                groups=host_data.get('groups', ''),
                nebula_ip=NebulaIP(
                    ipv4=host_data.get('nebula_ip', {}).get('ipv4'),
                    ipv6=host_data.get('nebula_ip', {}).get('ipv6')
                ),
                port=host_data.get('port', '4242'),
                public_ip=host_data.get('public_ip'),
                name=host_name
            )
    
    return NebulaConfig(
        net_name=config_dict.get('net-name', ''),
        relay_servers=config_dict.get('relay_servers', []),
        ca_pem=config_dict.get('ca_pem', ''),
        in_pub=config_dict.get('in_pub', ''),
        ca_key_path=config_dict.get('ca_key_path', ''),
        blocklist=config_dict.get('blocklist', []),
        lighthouse=config_dict.get('lighthouse', {}),
        hosts=config_dict.get('hosts', {})
    )


def validate_config_safe(config_dict: dict) -> tuple:
    """Безопасная валидация (не бросает исключение)."""
    try:
        validate_config(config_dict)
        return True, ""
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent / "config-nebula.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        is_valid, error = validate_config_safe(config)
        if is_valid:
            print("Конфиг валиден")
        else:
            print(f"Ошибка валидации: {error}")
    
    # Тест на невалидный конфиг
    test_configs = [
        {
            'net-name': 'test',
            'hosts': {
                'test-host': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.1/24'},
                    'port': '70000'
                }
            }
        },
        {
            'net-name': 'test',
            'hosts': {
                'test-host': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': 'invalid-ip'},
                    'port': '4242'
                }
            }
        },
        {
            'net-name': '',
            'hosts': {
                'test-host': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.1/24'},
                    'port': '4242'
                }
            }
        }
    ]
    
    print("\n--- Тесты валидации ---")
    for i, cfg in enumerate(test_configs):
        is_valid, error = validate_config_safe(cfg)
        if is_valid:
            print(f"Тест {i+1}: Валиден")
        else:
            print(f"Тест {i+1}: Ошибка: {error}")
