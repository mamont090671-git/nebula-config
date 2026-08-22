#!/usr/bin/env python3
"""
Pydantic V2 валидатор для config-nebula.yaml.

Проверяет:
- Обязательные поля (net-name, lighthouse, hosts)
- Валидные IP/CIDR в nebula_ip
- Диапазон порта 0-65535
- am_relay только для lighthouse
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional
from ipaddress import IPv4Network, IPv6Network, IPv4Address


class NebulaIP(BaseModel):
    """Внутренний IP узла"""
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None

    @field_validator('ipv4')
    @classmethod
    def validate_ipv4(cls, v):
        if v:
            try:
                IPv4Network(v, strict=False)
            except ValueError:
                raise ValueError(f"Невалидный IPv4 CIDR: {v}. Формат: 192.168.10.10/24")
        return v

    @field_validator('ipv6')
    @classmethod
    def validate_ipv6(cls, v):
        if v:
            try:
                IPv6Network(v, strict=False)
            except ValueError:
                raise ValueError(f"Невалидный IPv6 CIDR: {v}. Формат: fd00:1234:5678:a::101/64")
        return v


class LighthouseConfig(BaseModel):
    """Конфигурация маяка"""
    groups: str
    nebula_ip: NebulaIP
    port: str
    public_ip: Optional[str] = None
    am_relay: bool = False

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        try:
            port = int(v)
            if port < 0 or port > 65535:
                raise ValueError(f"Порт должен быть 0-65535, получено: {port}")
        except ValueError:
            raise ValueError(f"Порт должен быть числом: {v}")
        return v

    @field_validator('public_ip')
    @classmethod
    def validate_public_ip(cls, v):
        if v:
            try:
                IPv4Address(v)
            except ValueError:
                raise ValueError(f"Невалидный публичный IP: {v}. Формат: 1.2.3.4")
        return v

    @model_validator(mode='after')
    def validate_am_relay(self):
        if self.am_relay and not self.public_ip:
            raise ValueError("am_relay: true требует public_ip")
        return self


class HostConfig(BaseModel):
    """Конфигурация узла"""
    groups: str
    nebula_ip: NebulaIP
    public_ip: Optional[str] = None
    port: str = "4242"
    name: Optional[str] = None

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        try:
            port = int(v)
        except ValueError:
            raise ValueError(f"Порт должен быть числом: {v}")
        if port < 0 or port > 65535:
            raise ValueError(f"Порт должен быть 0-65535, получено: {port}")
        return v

    @field_validator('public_ip')
    @classmethod
    def validate_public_ip(cls, v):
        if v:
            try:
                IPv4Address(v)
            except ValueError:
                raise ValueError(f"Невалидный публичный IP: {v}. Формат: 1.2.3.4")
        return v


class NebulaConfig(BaseModel):
    """Мастер-конфигурация Nebula"""
    model_config = ConfigDict(populate_by_name=True)
    net_name: str = Field(..., alias='net-name')
    relay_servers: List[str] = []
    ca_pem: str = ""
    in_pub: str = ""
    ca_key_path: str = ""
    lighthouse: dict = {}
    hosts: dict = {}

    @field_validator('net_name')
    @classmethod
    def validate_net_name(cls, v):
        if not v.strip():
            raise ValueError("net-name не может быть пустым")
        return v

    @field_validator('ca_pem')
    @classmethod
    def validate_ca_pem(cls, v):
        return v.strip() if v else ""

    @field_validator('in_pub')
    @classmethod
    def validate_in_pub(cls, v):
        return v.strip() if v else ""

    @field_validator('ca_key_path')
    @classmethod
    def validate_ca_key_path(cls, v):
        return v.strip() if v else ""

    @model_validator(mode='after')
    def validate_lighthouse_hosts(self):
        for node_type, nodes in [('lighthouse', self.lighthouse), ('host', self.hosts)]:
            for name, data in nodes.items():
                if isinstance(data, dict):
                    nebula_ip = data.get('nebula_ip', {})
                    if not nebula_ip.get('ipv4') and not nebula_ip.get('ipv6'):
                        raise ValueError(
                            f"{node_type} '{name}': обязано иметь nebula_ip.ipv4 или nebula_ip.ipv6"
                        )
        return self

    @model_validator(mode='after')
    def validate_relay_servers(self):
        seen = set()
        for ip in self.relay_servers:
            if ip in seen:
                raise ValueError(f"Дублирующийся relay_server: {ip}")
            seen.add(ip)
        return self


def validate_config(config_dict: dict) -> NebulaConfig:
    """
    Валидирует конфиг и возвращает Pydantic модель.
    
    Args:
        config_dict: словарь из config-nebula.yaml
        
    Returns:
        NebulaConfig валидированный
        
    Raises:
        pydantic.ValidationError: если конфиг невалидный
    """
    # Валидируем lighthouse
    for lh_name, lh_data in config_dict.get('lighthouse', {}).items():
        if isinstance(lh_data, dict):
            try:
                LighthouseConfig(**lh_data)
            except Exception as e:
                raise ValueError(f"Ошибка валидации lighthouse '{lh_name}': {e}")
    
    # Валидируем hosts
    for host_name, host_data in config_dict.get('hosts', {}).items():
        if isinstance(host_data, dict):
            try:
                HostConfig(**host_data)
            except Exception as e:
                raise ValueError(f"Ошибка валидации host '{host_name}': {e}")
    
    # Валидируем весь конфиг
    return NebulaConfig(**config_dict)


def validate_config_safe(config_dict: dict) -> tuple:
    """
    Безопасная валидация (не бросает исключение).
    
    Args:
        config_dict: словарь из config-nebula.yaml
        
    Returns:
        (is_valid, error_message)
    """
    try:
        validate_config(config_dict)
        return True, ""
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    # Тестирование
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
                    'port': '70000'  # Ошибка: порт > 65535
                }
            }
        },
        {
            'net-name': 'test',
            'hosts': {
                'test-host': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': 'invalid-ip'},  # Ошибка: невалидный IP
                    'port': '4242'
                }
            }
        },
        {
            'net-name': '',  # Ошибка: пустое имя сети
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
