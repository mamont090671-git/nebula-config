# Nebula VPN Config Generator

Configuration generator for [Nebula VPN](https://github.com/slackhq/nebula) network in Python. Automatically creates node configurations, certificates, and verifies correctness from a single master config file.

## Features

- **Automatic configuration generation** from `config-nebula.yaml`
- **Certificate generation** for CA and all nodes (V2 format)
- **Static host maps** with IPv4 and IPv6 support
- **Post-generation verification** — auto-checks relay, use_relays, static_host_map, IPv6 hosts
- **Relay support** — automatic relays generation for NAT hosts
- **Parameterized deploy scripts** — deploy.sh accepts target path as argument
- **Inline CA** — embedded CA PEM directly in config
- **Key-based signing** — `-in-pub` support for certificate signing
- **Backup support** — automatic backup of existing configs

## Requirements

- Python 3.8+
- Nebula v2 binaries (`nebula-cert` from https://github.com/slackhq/nebula/releases)
- IPv6 support requires Nebula build with IPv6 support

## Project Structure

```
nebula-config/
├── config-nebula.yaml          # Network master config
├── generate_configs.py         # Main config generator
├── generate_deploy.sh          # Deploy script generator
├── example-config.yml          # Example master config
├── todo-later.md               # Future tasks
├── plan-fixes.md               # Completed fixes plan
├── for-all/
│   ├── nebula                  # Nebula binary
│   ├── nebula-cert             # Certificate binary
│   └── nebula_service.sh       # systemd service script
├── host/
│   └── config.yaml             # Host node template
├── lighthouse/
│   └── config.yaml             # Lighthouse node template
├── output/                     # Generated configurations
│   ├── ca/                     # CA certificates
│   ├── node-name/              # Per-node configs
│   └── lighthouse-name/        # Per-lighthouse configs
└── README.md
```

## Configuration Format

Create `config-nebula.yaml` with the following structure:

```yaml
net-name: my-network

# Relay servers — nebula IPs of nodes through which NAT clients relay
relay_servers:
  - 192.168.10.101

# Inline CA PEM (base64, optional)
ca_pem: ""

# Key-based signing public address (optional)
in_pub: ""

lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.10/24
      ipv6: fd00:1234:5678:a::10/64
    port: '4242'
    public_ip: 1.2.3.4
    am_relay: true        # true for relay lighthouse
    type: LH

hosts:
  server-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    public_ip: 9.10.11.12
    port: '4242'           # 4242 = public IP, 0 = behind NAT
    type: HOST
  laptop-1:
    groups: home,ssh,admins
    name: laptop-1
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    port: '0'              # 0 = behind NAT, will use relay
    type: HOST
```

### Configuration Fields

| Field | Description |
|-------|-------------|
| `net-name` | Network name used in CA certificate |
| `relay_servers` | List of relay server nebula IPs for NAT hosts |
| `ca_pem` | Inline CA PEM (if empty, uses /etc/nebula/ca.crt) |
| `in_pub` | Public address for `-in-pub` (key-based signing) |
| `lighthouse` | Lighthouse node configurations |
| `hosts` | Regular host configurations |
| `groups` | Comma-separated access group names |
| `nebula_ip.ipv4` | Internal IPv4 address with CIDR |
| `nebula_ip.ipv6` | Internal IPv6 address with CIDR |
| `port` | Port: `4242` for public IPs, `0` for NAT |
| `public_ip` | Public IP (for public nodes/lighthouses) |
| `am_relay` | `true` for relay lighthouse |
| `name` | Certificate name (defaults to node name) |

### Relay Architecture

For hosts behind NAT (port 0), relay is mandatory:

**On relay lighthouse:**
```yaml
relay:
  am_relay: true
  use_relays: false
```

**On NAT client (automatic):**
```yaml
relays:
  - 192.168.10.101
relay:
  use_relays: true
```

## Usage

### Generate All Configurations

```bash
cd /path/to/nebula-config
python3 generate_configs.py
```

This will:
1. Check/create CA
2. Generate configurations for all nodes and lighthouses
3. Create `*.crt` and `*.key` files for each node
4. Copy `ca.crt` to each node directory
5. **Run verification** — check relay, use_relays, static_host_map, IPv6 hosts

### Generate CA Certificate Only

```bash
python3 generate_configs.py --generate-ca
```

### Generate Certificates for Specific Nodes

```bash
python3 generate_configs.py --host server-1 laptop-1
python3 generate_configs.py --light light-1
python3 generate_configs.py --only-hosts --host server-1
python3 generate_configs.py --only-lights --light light-1
```

### Generate All Certificates Without Configs

```bash
python3 generate_configs.py --generate-host-certs
```

### Use Custom nebula-cert Path

```bash
python3 generate_configs.py --cert-path /path/to/nebula-cert
```

### Generate Deploy Scripts

```bash
bash generate_deploy.sh
```

Creates `deploy.sh` in each node/lighthouse directory under `output/`.

### Use deploy.sh

```bash
cd output/server-1
./deploy.sh                    # to /etc/nebula/ (default)
./deploy.sh /custom/path/      # to specified path
```

## Output Directory Structure

After generation, `output/` contains:

```
output/
├── ca/
│   ├── ca.crt              # CA certificate
│   └── ca.key              # CA private key
├── server-1/
│   ├── ca.crt              # CA certificate (verification)
│   ├── config.yaml         # Node configuration
│   ├── server-1.crt        # Node certificate
│   ├── server-1.key        # Node private key
│   ├── nebula              # Nebula binary
│   ├── nebula-cert         # Nebula-cert binary
│   ├── nebula_service.sh   # systemd service script
│   └── deploy.sh           # Deploy script
└── light-1/
    ├── ca.crt
    ├── config.yaml
    ├── light-1.crt
    ├── light-1.key
    ├── nebula
    ├── nebula-cert
    ├── nebula_service.sh
    └── deploy.sh
```

## Deployment

### Deploy to Target Server

```bash
cd output/server-1
./deploy.sh          # copies to /etc/nebula/
```

### Manual Deployment

1. Copy files from `output/server-1/` to target server
2. Place files in `/etc/nebula/`:
   ```bash
   sudo cp -r /path/to/output/server-1/* /etc/nebula/
   sudo chmod +x /etc/nebula/nebula /etc/nebula/nebula-cert
   ```
3. Create systemd service:
   ```bash
   sudo cp /etc/nebula/nebula_service.sh /etc/systemd/system/nebula.service
   sudo systemctl daemon-reload
   sudo systemctl enable nebula
   sudo systemctl start nebula
   ```

## Certificate Generation

### CA Certificate

```bash
./for-all/nebula-cert ca -name "my-network" -version 2 -out-key ca.key -out-crt ca.crt
```

### Node Certificate

```bash
./for-all/nebula-cert sign \
  -name "server-1" \
  -ip "192.168.10.100/24,fd00:1234:5678:a::100/64" \
  -groups "home,ssh" \
  -ca-crt ca.crt \
  -ca-key ca.key \
  -out-crt server-1.crt \
  -out-key server-1.key
```

## Verification

After every generation, automatic verification runs:

- relay_servers is not empty (if NAT hosts with port 0 exist)
- port 0 hosts have `use_relays: true` and `relay:` section
- relay lighthouse has `am_relay: true` and `use_relays: false`
- static_host_map is populated for all clients
- IPv6 hosts section contains all lighthouses

## Troubleshooting

### "CA not found" Error

```bash
python3 generate_configs.py --generate-ca
```

### "nebula-cert not found" Error

```bash
python3 generate_configs.py --cert-path /path/to/nebula-cert
```

### Regenerate Everything

```bash
rm -rf output/*
python3 generate_configs.py
```

## Security Recommendations

- Keep `ca.key` secure and offline
- Distribute `ca.crt` only for adding new nodes
- Node certificates and keys can be safely distributed to their owners
- Use separate groups for different access levels
- Rotate certificates regularly

## License

This project is provided "as is" for managing Nebula VPN configurations.

## Contributing

Issues and pull requests are welcome. Please ensure your changes maintain compatibility with existing functionality.
