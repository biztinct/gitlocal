# Code Protection — Deployment Runsheet

> **Last Updated:** 2026-02-26
> **Author:** Biztinct Engineering

---

## 1. Environment Overview

| Environment | Machine | OS | Python | Role |
|---|---|---|---|---|
| **Development** | Mac (local) | macOS, x86_64 | 3.14 | Write code, push to Git, generate licenses |
| **Testing / Build** | Payobook19 | Ubuntu 22.04, x86_64 | 3.10 | **Compile obfuscated code**, test, stage releases |
| **Client** | Client Server | Ubuntu (behind VPN) | 3.10 (expected) | Run production Odoo with protected code |

---

## 2. Recommendation: Compile on Payobook19 (Option A)

### Why NOT compile on Mac?

| Constraint | Mac | Payobook19 |
|---|---|---|
| Python version | 3.14 ❌ (mismatch with servers) | 3.10 ✅ (matches client) |
| OS & Architecture | macOS ❌ (cross-compile needed) | Linux x86_64 ✅ (same as client) |
| PyArmor BCC mode | ❌ Cannot cross-compile | ✅ Full support (strongest protection) |
| All Odoo modules present? | ❌ Limited dev subset | ✅ Complete set |
| Can test obfuscated code? | ❌ No (different runtime) | ✅ Yes (verify before shipping) |

**Verdict:** PyArmor bytecode is locked to the Python version and OS it was compiled on.
Your Mac runs Python 3.14 on macOS. Your servers run Python 3.10 on Linux.
Code obfuscated on Mac will **never run** on either server.
**Payobook19 is the only viable compilation machine.**

### What stays on each machine

| Task | Where |
|---|---|
| Write / edit source code | Mac |
| Push code to server | Mac → Payobook19 (rsync / deploy script) |
| Generate RSA keypair | Mac (one-time, already done) |
| Generate signed license.json | Mac (uses private key — never leaves Mac) |
| Install PyArmor | Payobook19 |
| **Compile obfuscated release** | **Payobook19** |
| Test obfuscated modules | Payobook19 |
| Transfer release to client | Payobook19 → Client (SCP over VPN) |
| Collect hardware fingerprint | Client server |
| Deploy license.json | Client server |

---

## 3. One-Time Setup (Do This Once)

### 3A. Install PyArmor on Payobook19

```bash
# SSH into Payobook19
ssh Payobook19

# Install PyArmor
sudo pip3 install pyarmor pyarmor.cli.core

# (Recommended) Activate PyArmor Pro license for full module support
# pyarmor reg /path/to/pyarmor-license.zip

# Verify
pyarmor --version
```

### 3B. Copy Build Tools to Payobook19

```bash
# From your Mac, copy the build scripts to Payobook19
scp vendor_license_core/tools/build_release.sh    Payobook19:/odoo/odoo-server/addons/vendor_license_core/tools/
scp vendor_license_core/tools/deploy_client.sh     Payobook19:/odoo/odoo-server/addons/vendor_license_core/tools/
scp vendor_license_core/tools/collect_fingerprint.py Payobook19:/odoo/odoo-server/addons/vendor_license_core/tools/
scp vendor_license_core/tools/generate_license.py  Payobook19:/odoo/odoo-server/addons/vendor_license_core/tools/

# Make executable
ssh Payobook19 "chmod +x /odoo/odoo-server/addons/vendor_license_core/tools/*.sh"
```

### 3C. Generate RSA Keypair (Already Done — Skip If Keys Exist)

```bash
# On your Mac (keys stay here, private key NEVER leaves Mac)
cd vendor_license_core/tools
python3 generate_keypair.py

# Embed the public key into crypto.py (already done)
```

---

## 4. Client Onboarding Runsheet

Use this checklist every time you onboard a new client.

### Step 1 — Collect Client Fingerprint
**Where:** Client server (over VPN)

```bash
# Copy the fingerprint script to the client
scp collect_fingerprint.py client_user@client_server:/tmp/

# SSH into client and run it
ssh client_user@client_server "python3 /tmp/collect_fingerprint.py"
```

**Expected output:**
```
═══════════════════════════════════════════════
  SERVER FINGERPRINT
═══════════════════════════════════════════════

  Fingerprint Hash: abc123def456...

  Send the Fingerprint Hash to your software vendor
═══════════════════════════════════════════════
```

📋 **Copy the Fingerprint Hash** — you'll need it in Step 2.

---

### Step 2 — Generate Signed License
**Where:** Mac (your local dev machine — has the private key)

```bash
cd vendor_license_core/tools

python3 generate_license.py \
    --customer "Client Company Name" \
    --fingerprint "abc123def456..." \
    --expiry "2027-12-31" \
    --max-employees 500 \
    --private-key "keys/private_key.pem" \
    --output "license_CLIENT.json"
```

📋 **Output:** `license_CLIENT.json` — you'll transfer this to the client in Step 5.

---

### Step 3 — Push Latest Code to Payobook19
**Where:** Mac

```bash
# Use your existing /deploy workflow to push latest code
# Or manually rsync the modules:
cd /Users/adity/Documents/GitHub/gitlocal

MODULES="vendor_license_core pb_hr_payroll_formula om_hr_payroll pb_hr_payroll_base pb_hr_workforce pb_hr_flow pb_hr_payroll_analytics pb_hr_govt payroll_analytics_approval"

for mod in $MODULES; do
    rsync -avz --delete --exclude='__pycache__' --exclude='*.pyc' \
        "$mod/" "Payobook19:/odoo/odoo-server/addons/$mod/"
done
```

---

### Step 4 — Compile Obfuscated Release
**Where:** Payobook19

```bash
ssh Payobook19

cd /odoo/odoo-server/addons

# Build the protected release
./vendor_license_core/tools/build_release.sh /tmp/client_release

# ═══════════════════════════════════════════════
#   Building Release (OBFUSCATED — PyArmor RFT+BCC)
#   Output: /tmp/client_release
# ═══════════════════════════════════════════════
#   ✅ Build Complete!
```

📋 **Output:** `/tmp/client_release/` folder containing:
- 9 obfuscated module directories
- `pyarmor_runtime_XXXXXX/` runtime folder
- `checksums.json` integrity manifest

**Verify** the obfuscation worked:
```bash
# Should show unreadable binary, NOT Python code
cat /tmp/client_release/vendor_license_core/models/license_state.py
```

**(Optional) Test on Payobook19 before shipping:**
```bash
# Temporarily install the obfuscated build on Payobook19 itself
sudo service odoo-server stop

for mod in vendor_license_core pb_hr_payroll_formula om_hr_payroll pb_hr_payroll_base pb_hr_workforce pb_hr_flow pb_hr_payroll_analytics pb_hr_govt payroll_analytics_approval; do
    sudo cp -r /odoo/odoo-server/addons/$mod /tmp/backup_$mod     # backup originals
    sudo rm -rf /odoo/odoo-server/addons/$mod
    sudo cp -r /tmp/client_release/$mod /odoo/odoo-server/addons/$mod
    sudo chown -R odoo:odoo /odoo/odoo-server/addons/$mod
done

# Copy the PyArmor runtime so Python can find it
sudo cp -r /tmp/client_release/pyarmor_runtime_* /usr/local/lib/python3.10/dist-packages/

# Restart and test
sudo service odoo-server start

# After testing, restore originals:
# for mod in ...; do sudo rm -rf /odoo/odoo-server/addons/$mod && sudo mv /tmp/backup_$mod /odoo/odoo-server/addons/$mod; done
```

---

### Step 5 — Transfer to Client
**Where:** Payobook19 → Client server (over VPN)

```bash
# From Payobook19, transfer the release to the client
scp -r /tmp/client_release client_user@client_server:/tmp/client_release

# Also transfer the license (from your Mac)
# On Mac:
scp vendor_license_core/tools/license_CLIENT.json client_user@client_server:/tmp/license.json
```

---

### Step 6 — Install on Client Server
**Where:** Client server (over VPN)

```bash
ssh client_user@client_server

# ── 6A. Setup License Directory ──
sudo mkdir -p /opt/vendor_license
sudo chown root:odoo /opt/vendor_license
sudo chmod 750 /opt/vendor_license

# Place license file
sudo mv /tmp/license.json /opt/vendor_license/license.json
sudo chown root:odoo /opt/vendor_license/license.json
sudo chmod 640 /opt/vendor_license/license.json

# Place integrity manifest
sudo mv /tmp/client_release/checksums.json /opt/vendor_license/checksums.json
sudo chown root:odoo /opt/vendor_license/checksums.json
sudo chmod 640 /opt/vendor_license/checksums.json

# ── 6B. Install PyArmor Runtime Globally ──
PY_DIR=$(python3 -c 'import site; print(site.getsitepackages()[0])')
sudo cp -r /tmp/client_release/pyarmor_runtime_* "$PY_DIR/"
sudo chmod -R 755 "$PY_DIR"/pyarmor_runtime_*

# ── 6C. Deploy Modules ──
ODOO_ADDONS="/odoo/odoo-server/addons"   # Adjust if client uses different path
MODULES="vendor_license_core pb_hr_payroll_formula om_hr_payroll pb_hr_payroll_base pb_hr_workforce pb_hr_flow pb_hr_payroll_analytics pb_hr_govt payroll_analytics_approval"

sudo service odoo-server stop

for mod in $MODULES; do
    sudo rm -rf "$ODOO_ADDONS/$mod"
    sudo cp -r "/tmp/client_release/$mod" "$ODOO_ADDONS/$mod"
    sudo chown -R odoo:odoo "$ODOO_ADDONS/$mod"
done

# ── 6D. Upgrade modules in Odoo ──
sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf \
    -d CLIENT_DB_NAME \
    -u vendor_license_core,pb_hr_payroll_formula,om_hr_payroll,pb_hr_payroll_base,pb_hr_workforce,pb_hr_flow,pb_hr_payroll_analytics,pb_hr_govt,payroll_analytics_approval \
    --stop-after-init --no-http

# ── 6E. Restart Odoo ──
sudo service odoo-server start
```

---

### Step 7 — Verify on Client
**Where:** Client server

```bash
# 1. Verify code is unreadable
cat /odoo/odoo-server/addons/vendor_license_core/models/license_state.py
# → Should show binary PyArmor data, NOT Python code

# 2. Verify license status
# Log into Odoo → Settings → Technical → Vendor License → License Status
# → Should show "Valid" with green ribbon

# 3. Verify Payroll works
# Click Payroll menu → Process a payslip → Everything should work normally
```

---

## 5. Update Runsheet (Pushing Code Updates to Existing Client)

When you release new features or bug fixes:

| Step | Where | Command |
|---|---|---|
| 1. Push latest code | Mac → Payobook19 | `rsync` or `/deploy` workflow |
| 2. Recompile | Payobook19 | `./build_release.sh /tmp/client_release` |
| 3. (Optional) Test | Payobook19 | Verify obfuscated code runs |
| 4. Transfer | Payobook19 → Client | `scp -r /tmp/client_release client:` |
| 5. Install | Client | Replace modules, `odoo-bin -u`, restart |

**No need to regenerate the license** — it persists across code updates.
The `checksums.json` manifest must be regenerated (the build script does this automatically).

---

## 6. Emergency Revert to Plain Python

If obfuscation causes issues on the client and you need to debug:

```bash
# On Payobook19:
cd /odoo/odoo-server/addons
./vendor_license_core/tools/build_release.sh /tmp/plain_build --plain

# Transfer to client and install as usual (Steps 5-6 above)
```

This deploys readable Python. **License validation still works** even with plain code.

---

## 7. Quick Reference Card

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT PIPELINE                           │
│                                                                  │
│   MAC (Dev)              PAYOBOOK19 (Build)        CLIENT        │
│   ─────────              ────────────────          ──────        │
│                                                                  │
│   Write Code ──rsync──→  Compile (PyArmor)  ──scp──→ Install    │
│   Gen License ─────────────────────────────────────→ /opt/       │
│   Private Key            All Modules                 Fingerprint │
│   (NEVER leaves Mac)     Python 3.10                 Python 3.10 │
│                          PyArmor Pro                              │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────────┐│
│   │  GOLDEN RULE: Obfuscation runs where Python version        ││
│   │  matches the target. Payobook19 (3.10) → Client (3.10) ✅  ││
│   │  Mac (3.14) → Client (3.10) ❌ WILL NOT WORK              ││
│   └─────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```
