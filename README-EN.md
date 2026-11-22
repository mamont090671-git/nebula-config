# Nebula VPN Config Generator

[![CI](https://github.com/mamont090671-git/nebula-config/actions/workflows/ci.yml/badge.svg)](https://github.com/mamont090671-git/nebula-config/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/mamont090671-git/nebula-config)](https://github.com/mamont090671-git/nebula-config/releases/tag/v1.1.1)

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

## Installation

```bash
./setup.sh
```

Downloads Nebula binaries, installs Python dependencies, creates `output/ca/`.

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

### Renew Expiring Certificates

```bash
python3 generate_configs.py --renew-expiring
```

Finds certificates expiring within 30 days, deletes old `.crt`/`.key`, regenerates them via CA, and rewrites configs with updated inline CA. Reports how many certificates were renewed.

### Targeted Generation

```bash
python3 generate_configs.py --host server-1
python3 generate_configs.py --only-hosts --host A B
python3 generate_configs.py --only-lights --light A B
```

### All CLI Flags

```bash
# Generate all hosts and all lighthouses (explicit version of running without flags)
python3 generate_configs.py --all

# Only specified hosts + all lighthouses
python3 generate_configs.py --host server-1 server-2

# All hosts + specified lighthouses
python3 generate_configs.py --light lh-1 lh-2

# Only hosts (no lighthouses)
python3 generate_configs.py --only-hosts --host A B

# Only lighthouses (no hosts)
python3 generate_configs.py --only-lights --light X Y

# Generate CA certificate
python3 generate_configs.py --generate-ca

# Generate certificates for all hosts
python3 generate_configs.py --generate-host-certs

# Check certificate expiry
python3 generate_configs.py --check-certs

# Auto-renew certificates expiring within 30 days
python3 generate_configs.py --renew-expiring

# Deploy to remote servers via ssh_target
python3 generate_configs.py --push

# Preview --push changes without deploying
python3 generate_configs.py --push --dry-run

# Specify path to nebula-cert (if not in PATH)
python3 generate_configs.py --cert-path /path/to/nebula-cert
```

### Deploy to Remote Servers

```bash
python3 generate_configs.py --push
```

**Preview before deploy:**

```bash
python3 generate_configs.py --push --dry-run
```

Shows which nodes and files would change, without actually deploying.

**Automatically:**
1. Detects remote architecture via SSH
2. Downloads Nebula binary
3. Copies configs + certificates
4. Creates systemd service
5. Restarts nebula and shows status

**Deploy safety:**
- Backup `config.yaml.bak` before replacing config
- **`nebula -test`** validation before startup
- If test fails — **auto-rollback** from backup, nebula **does not start**
- Server won't lose connectivity on config errors

**For auto-deploy** set `ssh_target` for each node in `config-nebula.yaml`:

```yaml
hosts:
  server-1:
    # ... other fields ...
    ssh_target: root@192.168.1.10:/etc/nebula
```

Format: `user@IP:/path/to/deploy`. If omitted — node is not auto-deployed, configs only in `output/`.

> **Important:** `ssh_target` works **with SSH keys only** (no password auth).
> Set up keys first:
> ```bash
> ssh-keygen -t ed25519
> ssh-copy-id root@192.168.1.10
> ```
> Passwords **cannot** be stored in config — insecure. For password auth use `sshpass` manually.

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

8 test classes, 31 tests:
- `TestNebulaIPValidation` (5): IPv4/IPv6 CIDR
- `TestHostConfigValidation` (7): port, public_ip, nebula_ip
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

MIT License — see [LICENSE](LICENSE) file.

## Recent Changes

Full changelog — [CHANGELOG.md](CHANGELOG.md).

Brief for 2026-11-22 (30 commits):
- **Security**: removed `shell=True` from all SSH/SCP commands, IPv6 validation, ssh_target format
- **Security**: mktemp instead of `/tmp/`, backup BEFORE deploy, local `nebula -test` validation
- **Fixes**: `--renew-expiring` node name, external_ca_key propagation, in_pub dict support
- **Fixes**: CA auto-generate with external_ca_key, atomic binary replacement (mv)
- **Cleanup**: dead code (compute_remote_file_hash, nebula_test), duplicate load_config() calls
- **Files**: unified systemd unit in `templates/nebula.service`, GitHub API for downloads
- **CI/CD**: ruff format/lint enforced
