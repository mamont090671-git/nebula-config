# Nebula VPN Config Generator

Python-based configuration generator for [Nebula VPN](https://github.com/slackhq/nebula) networks. Automatically generates node configurations and certificates from a single master configuration file.

## Features

- **Automatic configuration generation** from `config-nebula.yaml`
- **Certificate generation** for CA and all nodes (V2 format)
- **Static host maps** with IPv4 and IPv6 support
- **Deploy scripts** for easy deployment to target servers
- **Backup support** for existing configurations

## Requirements

- Python 3.8+
- Nebula v2 binary (`nebula-cert` from https://github.com/slackhq/nebula/releases)
- For IPv6 support, Nebula must support IPv6 in your build

## Project Structure

```
nebula-config/
├── config-nebula.yaml          # Master configuration file
├── generate_configs.py         # Main configuration generator
├── generate_deploy.sh          # Script to generate deploy scripts
├── for-all/
│   ├── nebula                  # Nebula binary
│   ├── nebula-cert             # Certificate generator binary
│   └── nebula_service.sh       # Systemd service script
├── host/
│   └── config.yaml             # Host node template
├── lighthouse/
│   └── config.yaml             # Lighthouse node template
├── output/                     # Generated configurations
│   ├── ca/                     # CA certificates
│   ├── node-name/              # Per-node configuration directories
│   └── lighthouse-name/        # Per-lighthouse configuration directories
├── host/
├── lighthouse/
└── README.md
```

## Configuration Format

Create `config-nebula.yaml` with the following structure:

```yaml
net-name: my-network
lighthouse:
  light-1:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.10/24
      ipv6: fd00:1234:5678:a::10/64
    port: '4242'
    public_ip: 1.2.3.4
    type: LH
  light-2:
    groups: home
    nebula_ip:
      ipv4: 192.168.10.11/24
      ipv6: fd00:1234:5678:a::11/64
    port: '4242'
    public_ip: 5.6.7.8
    type: LH
hosts:
  server-1:
    groups: home,ssh
    nebula_ip:
      ipv4: 192.168.10.100/24
      ipv6: fd00:1234:5678:a::100/64
    public_ip: 9.10.11.12
    type: HOST
  laptop-1:
    groups: home,ssh,admins
    name: laptop-1
    nebula_ip:
      ipv4: 192.168.10.101/24
      ipv6: fd00:1234:5678:a::101/64
    type: HOST
```

### Configuration Fields

| Field | Description |
|-------|-------------|
| `net-name` | Network name used in CA certificate |
| `lighthouse` | Lighthouse node configurations |
| `hosts` | Regular host configurations |
| `groups` | Comma-separated group names |
| `nebula_ip.ipv4` | Internal IPv4 address with CIDR |
| `nebula_ip.ipv6` | Internal IPv6 address with CIDR |
| `port` | Port for lighthouses (0 for clients) |
| `public_ip` | Public IP for NAT traversal (lighthouses) |
| `type` | `LH` for lighthouse, `HOST` for regular nodes |
| `name` | Certificate name (defaults to node name) |

## Usage

### Generate All Configurations

```bash
cd /path/to/nebula-config
python3 generate_configs.py
```

This will:
1. Create `output/ca/` directory and generate CA if not exists
2. Generate configurations for all nodes and lighthouses
3. Create `*.crt` and `*.key` files for each node
4. Copy `ca.crt` to each node directory

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

### Using Custom nebula-cert Path

```bash
python3 generate_configs.py --cert-path /path/to/nebula-cert
```

### Generate Deploy Scripts

```bash
bash generate_deploy.sh
```

This creates `deploy.sh` in each node/lighthouse directory in `output/`.

## Output Directory Structure

After generation, `output/` will contain:

```
output/
├── ca/
│   ├── ca.crt              # CA certificate
│   └── ca.key              # CA private key
├── server-1/
│   ├── ca.crt              # CA certificate (for verification)
│   ├── config.yaml         # Node configuration
│   ├── server-1.crt        # Node certificate
│   ├── server-1.key        # Node private key
│   ├── nebula              # Nebula binary
│   ├── nebula-cert         # Certificate binary
│   └── nebula_service.sh   # Systemd service script
└── light-1/
    ├── ca.crt
    ├── config.yaml
    ├── light-1.crt
    ├── light-1.key
    ├── nebula
    ├── nebula-cert
    └── nebula_service.sh
```

## Deployment

### Deploy to Target Server

```bash
cd output/server-1
./deploy.sh
```

This copies all necessary files to `/home/mamont/test-n/`.

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

## Troubleshooting

### "CA not found" Error

```bash
python3 generate_configs.py --generate-ca
```

### "nebula-cert not found" Error

```bash
python3 generate_configs.py --cert-path /path/to/nebula-cert
```

### Re-generate All

```bash
rm -rf output/*
python3 generate_configs.py
```

## Security Notes

- Keep `ca.key` secure and offline
- Only share `ca.crt` to add new nodes
- Node certificates and keys can be safely distributed to their respective hosts
- Use separate groups for different access levels
- Rotate certificates periodically

## License

This project is provided as-is for managing Nebula VPN configurations.

## Contributing

Issues and pull requests welcome. Please ensure your changes maintain compatibility with existing functionality.
