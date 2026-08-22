# Nebula VPN Config Generator

Configuration generator for [Nebula VPN](https://github.com/slackhq/nebula) network in Python. Creates configurations, certificates, and deploys to servers from a single master config file.

## Features

- **Configuration generation** from `config-nebula.yaml`
- **Pydantic validation** — CIDR, port 0-65535, required fields
- **Auto-strip CIDR masks** via `ipaddress` stdlib
- **SSH-based deployment** — `--push` deploy to remote servers
- **Dynamic Ansible Inventory** — `nebula_inventory.py`
- **Inline CA** — CA PEM embedded directly in config
- **Key-based signing** — `-in-pub` support
- **Offline CA** — `ca_key_path` for external key
- **Systemd hardening** — least privilege, `ProtectSystem=strict`
- **CI/CD** — ruff + pytest on every push
- **Security** — `ca_key_path` for offline CA

## Requirements

- Python 3.8+
- Nebula v2 binaries: `bash setup-binaries.sh`
- For deployment: `sshpass` or configured SSH keys

## Project Structure

```
nebula-config/
├── config-nebula.yaml          # Network master config
├── generate_configs.py         # Main config generator (+ --push)
├── validators.py               # Pydantic config validation
├── nebula_inventory.py         # Dynamic Ansible inventory
├── setup-binaries.sh           # Nebula binary downloader
├── templates/
│   └── config.yaml             # Unified config template (DO NOT MODIFY)
├── for-all/
│   └── nebula_service.sh       # systemd service (hardened)
├── tests/
│   └── test_config.py          # 23 pytest tests
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
├── output/                     # Generated configs (gitignore)
└── plan-fixes.md               # Completed tasks plan
```

> `output/`, `__pycache__/` in `.gitignore`. Before use: `bash setup-binaries.sh`

## Configuration Format

```yaml
net-name: x-net

# Relay servers for NAT hosts
relay_servers:
  - 192.168.10.101

# Inline CA PEM (optional)
ca_pem: ""

# Key-based signing public address (optional)
in_pub: ""

# External CA key (optional). If set, CA generation is skipped.
ca_key_path: ""

lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: '4242'
    public_ip: 138.100.15.25
    am_relay: true
    type: LH

hosts:
  NL-H:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    public_ip: 31.58.33.31
    port: '4242'
    type: HOST
    # ssh_target: user@1.2.3.4:/etc/nebula

  laptop-1:
    groups: home,ssh,admins
    nebula_ip:
      ipv4: 192.168.10.103/24
      ipv6: fd00:1234:5678:a::103/64
    port: '0'  # NAT host, uses relay
    type: HOST
```

### Fields

| Field | Description |
|-------|-------------|
| `net-name` | Network name for CA |
| `relay_servers` | Relay server IPs |
| `ca_pem` | Inline CA PEM |
| `in_pub` | Key-based signing |
| `ca_key_path` | Path to external CA key |
| `groups` | Access groups (comma-separated) |
| `nebula_ip` | Internal IP + CIDR |
| `port` | `4242` = public, `0` = NAT |
| `public_ip` | Public IP |
| `am_relay` | Relay lighthouse |
| `ssh_target` | `user@host:/etc/nebula` for `--push` |

### Relay Architecture

NAT hosts (`port: 0`) → `use_relays: true` + relay section. Relay lighthouse → `am_relay: true` + `use_relays: false`. Public hosts → `use_relays: false`.

## Usage

### Generate All Configurations

```bash
python3 generate_configs.py
```

Checks/creates CA → generates configs → creates certificates → verification.

### Targeted Generation

```bash
python3 generate_configs.py --host server-1
python3 generate_configs.py --only-hosts --host A B
python3 generate_configs.py --light light-1
```

### Deploy to Remote Servers

```bash
# Nodes with ssh_target in config will be deployed automatically
python3 generate_configs.py --push
```

Copies all files from `output/<node>/` to `ssh_target` + `systemctl restart nebula`.

### Dynamic Ansible Inventory

```bash
ansible-inventory --list -i nebula_inventory.py
ansible-playbook -i nebula_inventory.py deploy.yml --limit Nebula
ansible-playbook -i nebula_inventory.py deploy.yml --limit home
```

### Tests

```bash
# Run all tests
pytest tests/test_config.py -v

# 6 test classes, 23 tests:
# - TestNebulaIPValidation (5 tests): IPv4/IPv6 CIDR
# - TestHostConfigValidation (6 tests): port, public_ip, nebula_ip
# - TestLighthouseConfigValidation (2 tests): am_relay without public_ip
# - TestNebulaConfigValidation (4 tests): valid config, empty net-name, duplicate relays
# - TestValidateConfigSafe (3 tests): safe validation
# - TestRealConfigValidation (2 tests): real config, relay for NAT
```

### Generate CA

```bash
python3 generate_configs.py --generate-ca
python3 generate_configs.py --generate-host-certs
```

## Output Directory Structure

```
output/
├── ca/
│   ├── ca.crt
│   └── ca.key
├── server-1/
│   ├── config.yaml
│   ├── server-1.crt
│   ├── server-1.key
│   └── ca.crt
└── light-1/
    ├── config.yaml
    ├── light-1.crt
    └── light-1.key
```

Binaries are no longer copied to output. For systemd use `for-all/nebula_service.sh`.

## Deployment

### Via --push (automatic)

```bash
python3 generate_configs.py --push
```

### Manual

```bash
cd output/server-1
scp -r * user@1.2.3.4:/etc/nebula/
ssh user@1.2.3.4 "systemctl restart nebula"
```

### systemd Service (hardened)

```bash
# Copy to target server
sudo cp nebula_service.sh /etc/systemd/system/nebula.service
sudo systemctl daemon-reload
sudo systemctl enable nebula
sudo systemctl start nebula
```

Service runs as user `nebula` with limited capabilities:
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `ProtectSystem=strict`, `ProtectHome=true`, `NoNewPrivileges=true`
- `ReadWritePaths=/etc/nebula`

## Verification

Automatic checks after generation:
- relay_servers is not empty (with NAT hosts)
- port 0 hosts have `use_relays: true`
- relay lighthouse has `am_relay: true`
- static_host_map is populated
- IPv6 hosts section contains all lighthouses

## Security

- `ca_key_path` — external CA key (not generated in `output/ca/`)
- systemd hardening — `ProtectSystem=strict`, `NoNewPrivileges=true`
- Keep `ca.key` offline
- Rotate certificates regularly

## CI/CD

GitHub Actions: `ruff check` + `ruff format --check` + `pytest` on every push/PR to master/main.

## License

This project is provided "as is" for managing Nebula VPN configurations.

## Plan

See [plan-fixes.md](plan-fixes.md) — all tasks completed.
