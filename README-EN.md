# Nebula VPN Config Generator

Configuration generator for [Nebula VPN](https://github.com/slackhq/nebula) network in Python. Creates configurations, certificates, and deploys to servers from a single master config file.

## Features

- **Configuration generation** from `config-nebula.yaml`
- **Config validation** — CIDR, port 0-65535, required fields
- **Auto-strip CIDR masks** via `ipaddress` stdlib
- **SSH-based deployment** — `--push` deploy to remote servers
- **Dynamic Ansible Inventory** — `nebula_inventory.py`
- **Inline CA** — CA PEM embedded directly in config
- **Key-based signing** — `-in-pub` support
- **Offline CA** — `ca_key_path` for external key
- **Systemd hardening** — least privilege, `ProtectSystem=strict`
- **CI/CD** — ruff + pytest on every push

## Requirements

- Python 3.8+
- For deployment: `sshpass` or configured SSH keys

## Example Configuration (config-nebula.yaml)

```yaml
net-name: x-net

# Relay servers for NAT hosts
relay_servers:
  - 192.168.10.101

ca_pem: ""
in_pub: ""
ca_key_path: ""

lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: 4242
    public_ip: 138.100.15.25
    am_relay: true

hosts:
  # Public host (direct hole-punch)
  server-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    port: 4242
    public_ip: 31.57.105.170
    # ssh_target: user@31.57.105.170:/etc/nebula

  # NAT host (port 0 — needs relay)
  client-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.102/24
      ipv6: fd00:1234:5678:a::102/64
    port: 0
    # public_ip not needed — port 0
```

## Project Structure

```
nebula-config/
├── setup.sh                  # Install script (nebula binaries + pip)
├── generate_configs.py       # Main config generator (+ --push)
├── validators.py             # Config validation
├── nebula_inventory.py       # Dynamic Ansible inventory
├── nebula_service.sh         # Deploy script (binary + systemd)
├── templates/
│   └── config.yaml           # Unified config template
├── tests/
│   └── test_config.py        # 23 pytest tests
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI
├── output/                   # Generated configs (gitignore)
└── config-nebula.yaml        # Master config (gitignore)
```

> `output/`, `__pycache__/`, `config-nebula.yaml`, `*.key`, `*.pem`, `nebula`, `nebula-cert` are in `.gitignore`.

## Configuration Format

See `config-nebula.yaml` (not in repo) — contains `net-name`, `relay_servers`, `lighthouse` and `hosts` sections with fields:

| Field | Description |
|-------|-------------|
| `net-name` | Network name for CA |
| `relay_servers` | Relay server IPs |
| `ca_pem` | Inline CA PEM (optional) |
| `in_pub` | Key-based signing (optional) |
| `ca_key_path` | Path to external CA key (optional) |
| `blocklist` | SHA-256 fingerprints of revoked certificates (optional) |
| `groups` | Access groups (comma-separated) |
| `nebula_ip` | Internal IP + CIDR (ipv4/ipv6) |
| `port` | `4242` = public, `0` = NAT |
| `public_ip` | Public IP (for public nodes) |
| `am_relay` | Relay lighthouse (lighthouse only) |
| `ssh_target` | `user@host:/etc/nebula` for `--push` |

### Relay Architecture

NAT hosts (`port: 0`) → `use_relays: true` + `relays:` section.
Relay lighthouse → `am_relay: true` + `use_relays: false`.
Public hosts → `use_relays: false`.

## Usage

### Generate All Configurations

```bash
python3 generate_configs.py
```

Checks/creates CA → generates configs → creates certificates → verification.

### Certificate Check

```bash
python3 generate_configs.py --check-certs
```

Checks all `.crt` in `output/` via `nebula-cert print`, outputs a table with days remaining. Exit 1 if < 30 days.

### Targeted Generation

```bash
python3 generate_configs.py --host server-1
python3 generate_configs.py --only-hosts --host A B
python3 generate_configs.py --only-lights --light light-1
```

### Deploy to Remote Servers

```bash
python3 generate_configs.py --push
```

**Automatically:**
1. Detects remote architecture via SSH
2. Downloads Nebula binary
3. Copies configs + certificates
4. Creates systemd service
5. Restarts nebula and shows status

### Dynamic Ansible Inventory

```bash
ansible-inventory --list -i nebula_inventory.py
ansible-playbook -i nebula_inventory.py deploy.yml --limit Nebula
ansible-playbook -i nebula_inventory.py deploy.yml --limit home
```

### Tests

```bash
pytest tests/test_config.py -v
```

7 test classes, 31 tests:
- `TestNebulaIPValidation` (5): IPv4/IPv6 CIDR
- `TestHostConfigValidation` (6): port, public_ip, nebula_ip
- `TestLighthouseConfigValidation` (2): am_relay without public_ip
- `TestNebulaConfigValidation` (4): valid config, empty net-name, duplicate relays
- `TestValidateConfigSafe` (3): safe validation
- `TestRealConfigValidation` (2): real config, relay for NAT
- `TestBlocklistValidation` (5): SHA-256 fingerprint validation
- `TestCheckCertsParsing` (3): nebula-cert print output parsing

### Generate CA

```bash
python3 generate_configs.py --generate-ca
python3 generate_configs.py --generate-host-certs
```

## Output Directory Structure

Each `output/<node>/` contains:

| File | Description |
|------|-------------|
| `config.yaml` | Unified Nebula V2 config (pki, firewall, lighthouse, relay, static_host_map, tun) |
| `<name>.crt` | Node certificate |
| `<name>.key` | Private key |
| `ca.crt` | CA certificate |
| `nebula_service.sh` | Deploy script (binary + systemd, all to `/etc/nebula/`) |

## Deployment

### Via --push (automatic)

```bash
python3 generate_configs.py --push
```

### Manual

```bash
cd output/<node-name>
scp -r * user@remote-host:/etc/nebula/
ssh user@remote-host "sudo bash /etc/nebula/nebula_service.sh /etc/nebula"
```

### systemd Service (hardened)

Service runs with limited capabilities:
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE`
- `ProtectSystem=strict`, `ProtectHome=yes`, `NoNewPrivileges=true`
- `ReadWritePaths=/etc/nebula`

## Verification

Automatic checks after generation:
- relay_servers is not empty (with NAT hosts)
- port 0 hosts have `use_relays: true`
- relay lighthouse has `am_relay: true`
- static_host_map populated (lighthouse includes itself)
- IPv6 hosts section contains all lighthouses

## Security

- `ca_key_path` — external CA key (not generated in `output/ca/`)
- `blocklist` — certificate revocation by SHA-256 fingerprint
- systemd hardening — `ProtectSystem=strict`, `NoNewPrivileges=true`
- Keep `ca.key` offline
- Rotate certificates regularly
- To update blocklist without breaking tunnels: `systemctl reload nebula`

## CI/CD

GitHub Actions: `ruff check` + `ruff format --check` + `pytest` on every push/PR to master/main.

## License

This project is provided "as is" for managing Nebula VPN configurations.
