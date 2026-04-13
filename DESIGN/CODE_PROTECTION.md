# Comprehensive Code Protection & Licensing Guide

This document outlines the architecture, deployment process, and instructions for implementing the `vendor_license_core` code protection system in any Odoo application.

## 1. System Architecture

The code protection system operates on multiple layers to ensure maximum security while allowing seamless offline operation for the client.

### Layers of Protection

1. **Layer 1: Code Obfuscation (PyArmor)**
   - All protected `.py` files are obfuscated into encrypted bytecode.
   - **BCC Mode**: Python is compiled directly to C extensions (extremely difficult to reverse-engineer, faster execution).
   - **RFT Mode**: Variable and function names are mangled.

2. **Layer 2: Licensing (`vendor_license_core`)**
   - **Offline Validation**: No internet required. Client server validates the license locally.
   - **Hardware Fingerprint**: License is tied to a specific machine (MAC + machine-id + CPU). Cloning the DB to a new server will invalidate the license.
   - **RSA Signature**: The `license.json` file is cryptographically signed. Any tampering breaks the signature.
   - **Employee Limit**: Enforces a maximum active employee count.
   - **Grace Period**: 7-day grace period upon expiry to prevent sudden business disruption.

3. **Layer 3: File Integrity Checks**
   - SHA-256 checksums of all protected `.py` files.
   - Verified at startup and daily via cron. Detects if any obfuscated file has been replaced or tampered with.

4. **Layer 4: Audit Logging**
   - All validation events (passes, failures, tampering) are logged in the `vendor.license.log` model for audit trails.

---

## 2. Directory Structure

```text
vendor_license_core/
├── __init__.py
├── __manifest__.py
├── hooks/
│   └── startup.py              # Validates license post-init
├── models/
│   ├── license_state.py        # Singleton storing current license state
│   └── license_log.py          # Audit log for validation events
├── services/
│   ├── crypto.py               # RSA signature verification
│   ├── enforce.py              # @require_license decorator
│   ├── fingerprint.py          # Hardware ID generation
│   ├── integrity.py            # SHA-256 file integrity checks
│   └── validator.py            # Core license validation logic
├── tools/                      # Vendor tools (NOT deployed to client)
│   ├── build_release.sh        # PyArmor obfuscation & minification
│   ├── deploy_client.sh        # Deployment script
│   ├── generate_keypair.py     # Generates RSA keys
│   ├── generate_license.py     # Signs and generates license.json
│   └── collect_fingerprint.py  # Client script to get hardware ID
├── data/
│   └── cron.xml                # Daily validation cron
├── security/
│   └── ir.model.access.csv
└── views/
    └── license_views.xml       # Admin UI for license status
```

---

## 3. How to Implement in Another Application

To protect a new Odoo module, follow these steps:

### Step 1: Add Dependency
In your module's `__manifest__.py`, add `vendor_license_core` to the dependencies:
```python
    'depends': ['base', 'vendor_license_core'],
```

### Step 2: Decorate Critical Methods
Identify the critical business logic methods in your module and decorate them with `@require_license`.

```python
from odoo import models
from odoo.addons.vendor_license_core.services.enforce import require_license

class MyCriticalModel(models.Model):
    _inherit = 'my.critical.model'

    @require_license
    def action_confirm(self):
        # This code will only run if the license is valid
        return super().action_confirm()
```

### Step 3: Add to Build Script
In `vendor_license_core/tools/build_release.sh`, add your new module name to the `PROTECTED_MODULES` array so it gets obfuscated:
```bash
PROTECTED_MODULES=(
    vendor_license_core
    my_new_module
)
```

---

## 4. Initial Setup (Vendor Side)

*This is a one-time setup on your development machine.*

1. **Generate RSA Keypair:**
   ```bash
   cd vendor_license_core/tools
   python3 generate_keypair.py
   ```
   This creates `keys/private_key.pem` (KEEP SECRET) and `keys/public_key.pem`.

2. **Embed Public Key:**
   Open `keys/public_key.pem`, copy its contents, and paste it into the `_EMBEDDED_PUBLIC_KEY_PEM` variable inside `vendor_license_core/services/crypto.py`.

---

## 5. Client Deployment Workflow

When onboarding a new client or deploying an update, follow this strict sequence:

### Step A: Collect Client Fingerprint
Send the `collect_fingerprint.py` script to the client and ask them to run it on their Odoo server.
```bash
python3 collect_fingerprint.py
# Example Output: abc123def456...
```

### Step B: Generate License File (Vendor Side)
Run the generator script on your secure machine using the client's fingerprint:
```bash
cd vendor_license_core/tools
python3 generate_license.py \
    --customer "Acme Corp" \
    --fingerprint "abc123def456..." \
    --expiry "2027-12-31" \
    --max-employees 500
```
This generates `license.json`.

### Step C: Prepare the Server (Client Side)
The server needs a protected directory for the license. Run as root:
```bash
sudo mkdir -p /opt/vendor_license
sudo chown root:odoo /opt/vendor_license
sudo chmod 750 /opt/vendor_license
```
Place the `license.json` file inside:
```bash
sudo cp license.json /opt/vendor_license/
sudo chown root:odoo /opt/vendor_license/license.json
sudo chmod 640 /opt/vendor_license/license.json
```

### Step D: Build & Deploy the Code
Run the build script to obfuscate the Python files, minify the JS/CSS, and generate the integrity manifest (`checksums.json`).

**1. Create the Release:**
```bash
cd vendor_license_core/tools
./build_release.sh
```
This generates obfuscated code in `dist/`.

*(Optional: To deploy normal readable code for debugging, run `./build_release.sh --plain`)*

**2. Deploy to Client:**
```bash
./deploy_client.sh client_server_hostname
```
The script will copy the files, place the `checksums.json` in `/opt/vendor_license/`, upgrade the modules in Odoo, and restart the service.

---

## 6. Troubleshooting & Emergency Revert

### License Check Failed / System Blocked
- Go to Odoo **Settings -> Technical -> Vendor License -> License Status**.
- Check the error message (e.g., File Missing, Fingerprint Mismatch, Expired, Tampered).
- Check the **Audit Log** for historical failures.

### Reverting to Plain Python
If obfuscation causes a critical issue and you need to debug the raw Python code on a live server:
```bash
# 1. Build plain release
./vendor_license_core/tools/build_release.sh --plain

# 2. Deploy
./vendor_license_core/tools/deploy_client.sh client_server_hostname
```
*Note: This removes protection. Only use in emergencies.*
