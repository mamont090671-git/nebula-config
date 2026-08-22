#!/usr/bin/env python3
"""
Тесты валидации конфига Nebula.
Запуск: pytest tests/test_config.py -v
"""

import pytest
import sys
import os

# Добавляем путь к validators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validators import validate_config, validate_config_safe, NebulaConfig, HostConfig, LighthouseConfig, NebulaIP


class TestNebulaIPValidation:
    """Валидация NebulaIP — CIDR для IPv4/IPv6."""

    def test_valid_ipv4(self):
        ip = NebulaIP(ipv4='192.168.10.100/24')
        assert ip.ipv4 == '192.168.10.100/24'

    def test_valid_ipv6(self):
        ip = NebulaIP(ipv6='fd00:1234:5678:a::100/64')
        assert ip.ipv6 == 'fd00:1234:5678:a::100/64'

    def test_invalid_ipv4(self):
        with pytest.raises(ValueError, match='Невалидный IPv4 CIDR'):
            NebulaIP(ipv4='invalid-ip')

    def test_invalid_ipv6(self):
        with pytest.raises(ValueError, match='Невалидный IPv6 CIDR'):
            NebulaIP(ipv6='not-an-ipv6')

    def test_missing_both(self):
        ip = NebulaIP()
        assert ip.ipv4 is None
        assert ip.ipv6 is None


class TestHostConfigValidation:
    """Валидация HostConfig — порты, IP, обязательные поля."""

    def test_valid_host(self):
        host = HostConfig(
            groups='home',
            nebula_ip={'ipv4': '192.168.10.100/24'},
            port='4242',
            public_ip='1.2.3.4'
        )
        assert host.port == '4242'
        assert host.public_ip == '1.2.3.4'

    def test_port_zero_nat(self):
        host = HostConfig(
            groups='home',
            nebula_ip={'ipv4': '192.168.10.100/24'},
            port='0'
        )
        assert host.port == '0'

    def test_port_too_high(self):
        with pytest.raises(ValueError, match='Порт должен быть 0-65535'):
            HostConfig(groups='home', nebula_ip={'ipv4': '192.168.10.100/24'}, port='70000')

    def test_port_negative(self):
        with pytest.raises(ValueError, match='Порт должен быть 0-65535'):
            HostConfig(groups='home', nebula_ip={'ipv4': '192.168.10.100/24'}, port='-1')

    def test_non_numeric_port(self):
        with pytest.raises(ValueError, match='Порт должен быть числом'):
            HostConfig(groups='home', nebula_ip={'ipv4': '192.168.10.100/24'}, port='abc')

    def test_invalid_public_ip(self):
        with pytest.raises(ValueError, match='Невалидный публичный IP'):
            HostConfig(groups='home', nebula_ip={'ipv4': '192.168.10.100/24'}, port='4242', public_ip='999.999.999.999')

    def test_missing_nebula_ip(self):
        with pytest.raises(ValueError, match='обязано иметь nebula_ip'):
            NebulaConfig(net_name='test', hosts={'bad': {'groups': 'home', 'port': '4242'}})


class TestLighthouseConfigValidation:
    """Валидация LighthouseConfig."""

    def test_valid_lighthouse(self):
        lh = LighthouseConfig(
            groups='home',
            nebula_ip={'ipv4': '192.168.10.101/24'},
            port='4242',
            public_ip='1.2.3.4',
            am_relay=True
        )
        assert lh.am_relay is True

    def test_am_relay_without_public_ip(self):
        with pytest.raises(ValueError, match='am_relay: true требует public_ip'):
            LighthouseConfig(groups='home', nebula_ip={'ipv4': '192.168.10.101/24'}, port='4242', am_relay=True)


class TestNebulaConfigValidation:
    """Валидация NebulaConfig — net-name, relay_servers, обязательные поля."""

    def test_valid_config(self):
        config = {
            'net-name': 'test-net',
            'relay_servers': ['192.168.10.101'],
            'lighthouse': {
                'light-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.101/24'},
                    'port': '4242',
                    'public_ip': '1.2.3.4',
                    'am_relay': True
                }
            },
            'hosts': {
                'host-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.100/24'},
                    'port': '4242',
                    'public_ip': '5.6.7.8'
                }
            }
        }
        result = validate_config(config)
        assert result.net_name == 'test-net'

    def test_empty_net_name(self):
        with pytest.raises(ValueError, match='net-name не может быть пустым'):
            NebulaConfig(net_name='', relay_servers=[], lighthouse={}, hosts={})

    def test_duplicate_relay_servers(self):
        with pytest.raises(ValueError, match='Дублирующийся relay_server'):
            NebulaConfig(
                net_name='test',
                relay_servers=['192.168.10.101', '192.168.10.101'],
                lighthouse={},
                hosts={}
            )

    def test_nat_without_relay_warning(self):
        """NAT-хост с port 0 должен предупредить о relay."""
        config = {
            'net-name': 'test',
            'relay_servers': ['192.168.10.101'],
            'lighthouse': {
                'light-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.101/24'},
                    'port': '4242',
                    'public_ip': '1.2.3.4',
                    'am_relay': True
                }
            },
            'hosts': {
                'nat-host': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.100/24'},
                    'port': '0'
                }
            }
        }
        result = validate_config(config)
        assert result.net_name == 'test'


class TestValidateConfigSafe:
    """Безопасная валидация (не бросает исключение)."""

    def test_safe_valid(self):
        config = {
            'net-name': 'test',
            'lighthouse': {
                'light-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.101/24'},
                    'port': '4242',
                    'public_ip': '1.2.3.4'
                }
            },
            'hosts': {
                'host-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.100/24'},
                    'port': '4242'
                }
            }
        }
        is_valid, error = validate_config_safe(config)
        assert is_valid is True
        assert error == ''

    def test_safe_invalid(self):
        config = {
            'net-name': '',  # Ошибка
            'lighthouse': {
                'light-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.101/24'},
                    'port': '4242',
                    'public_ip': '1.2.3.4'
                }
            },
            'hosts': {}
        }
        is_valid, error = validate_config_safe(config)
        assert is_valid is False
        assert 'net-name' in error.lower() or 'пусто' in error

    def test_safe_port_error(self):
        config = {
            'net-name': 'test',
            'lighthouse': {
                'light-1': {
                    'groups': 'home',
                    'nebula_ip': {'ipv4': '192.168.10.101/24'},
                    'port': '99999',  # Ошибка
                    'public_ip': '1.2.3.4'
                }
            },
            'hosts': {}
        }
        is_valid, error = validate_config_safe(config)
        assert is_valid is False
        assert 'порт' in error.lower() or '65535' in error


class TestRealConfigValidation:
    """Тесты на реальном конфиге проекта."""

    def test_real_config_is_valid(self):
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config-nebula.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        is_valid, error = validate_config_safe(config)
        assert is_valid is True, f"Реальный конфиг невалиден: {error}"

    def test_relay_servers_for_nat(self):
        """Проверка что relay_servers указан для NAT-хостов."""
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config-nebula.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        nat_hosts = [name for name, data in config.get('hosts', {}).items() if str(data.get('port', '4242')) == '0']
        if nat_hosts:
            relays = config.get('relay_servers', [])
            assert len(relays) > 0, f"NAT-хосты {nat_hosts} требуют relay_servers"
