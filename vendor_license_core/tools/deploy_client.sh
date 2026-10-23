#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Deploy to Client Server
#
# Copies the built release (obfuscated or plain) to a client
# server and installs/upgrades the modules in Odoo.
#
# Prerequisites:
#   - SSH access to the target server
#   - build_release.sh has been run to create the dist/ folder
#   - License file has been deployed to /opt/vendor_license/
#
# Usage:
#   ./deploy_client.sh <server> [dist_dir]
#   ./deploy_client.sh payobook19             # → deploys from ./dist/
#   ./deploy_client.sh payobook19 /tmp/build  # → deploys from /tmp/build/
#
# Example Full Workflow:
#   1. ./build_release.sh                     # Build obfuscated release
#   2. ./deploy_client.sh payobook19          # Deploy to server
# ═══════════════════════════════════════════════════════════

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy_client.sh <ssh_server> [dist_dir]"
    echo "Example: ./deploy_client.sh payobook19"
    exit 1
fi

SERVER="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${2:-$(dirname "$SCRIPT_DIR")/dist}"

ODOO_ADDONS="/odoo/odoo-server/addons"
ODOO_CONF="/etc/odoo-server.conf"
ODOO_DB="$(ssh "$SERVER" "grep -oP 'db_name\s*=\s*\K\S+' $ODOO_CONF 2>/dev/null" || echo "")"
ODOO_BIN="/odoo/odoo-server/odoo-bin"

# Modules to deploy
MODULES=(
    vendor_license_core
    pb_hr_workforce
    pb_hr_flow
    om_hr_payroll
    pb_hr_payroll_base
    pb_hr_payroll_formula
    pb_hr_payroll_analytics
    pb_hr_govt
    payroll_analytics_approval
)

if [ ! -d "$DIST_DIR" ]; then
    echo "ERROR: Distribution directory not found: $DIST_DIR"
    echo "Run build_release.sh first."
    exit 1
fi

echo "═══════════════════════════════════════════════"
echo "  Deploying to: $SERVER"
echo "  Source:  $DIST_DIR"
echo "  Target:  $ODOO_ADDONS"
echo "  DB:      ${ODOO_DB:-auto-detect}"
echo "═══════════════════════════════════════════════"
echo

# ── Step 1: Upload modules ──
echo "── Step 1: Uploading modules ──"
for mod in "${MODULES[@]}"; do
    if [ -d "$DIST_DIR/$mod" ]; then
        echo "  Uploading $mod..."
        rsync -avz --delete "$DIST_DIR/$mod/" "$SERVER:/tmp/deploy_$mod/" > /dev/null 2>&1
    fi
done

# Upload PyArmor runtime if it exists
if ls "$DIST_DIR"/pyarmor_runtime* 1> /dev/null 2>&1; then
    for rtdir in "$DIST_DIR"/pyarmor_runtime*; do
        if [ -d "$rtdir" ]; then
            rtname=$(basename "$rtdir")
            echo "  Uploading $rtname..."
            rsync -avz --delete "$rtdir/" "$SERVER:/tmp/deploy_$rtname/" > /dev/null 2>&1
        fi
    done
fi
echo

# ── Step 2: Upload integrity manifest ──
if [ -f "$DIST_DIR/checksums.json" ]; then
    echo "── Step 2: Uploading integrity manifest ──"
    rsync -avz "$DIST_DIR/checksums.json" "$SERVER:/tmp/deploy_checksums.json" > /dev/null 2>&1
    echo "  checksums.json uploaded"
    echo
fi

# ── Step 3: Install on server ──
echo "── Step 3: Installing on server ──"
MOD_LIST=$(IFS=,; echo "${MODULES[*]}")

ssh "$SERVER" "sudo bash -c '
    # Copy modules to addons
    for mod in ${MODULES[*]}; do
        if [ -d /tmp/deploy_\$mod ]; then
            rm -rf $ODOO_ADDONS/\$mod
            cp -r /tmp/deploy_\$mod $ODOO_ADDONS/\$mod
            chown -R odoo:odoo $ODOO_ADDONS/\$mod
        fi
    done

    # Determine global Python dist-packages for PyArmor runtime
    PY_DIR=\$(python3 -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || echo '/usr/local/lib/python3.10/dist-packages')
    
    # Install PyArmor runtime globally so Odoo Python can import it
    for rtdir in /tmp/deploy_pyarmor_runtime*; do
        if [ -d "\$rtdir" ]; then
            rtname=\$(basename "\$rtdir" | sed 's/^deploy_//')
            
            # Put in global python packages
            rm -rf "\$PY_DIR/\$rtname"
            cp -r "\$rtdir" "\$PY_DIR/\$rtname"
            chown -R root:root "\$PY_DIR/\$rtname" 2>/dev/null || true
            chmod -R 755 "\$PY_DIR/\$rtname"
            
            # Also keep a copy in addons just in case it is loaded dynamically
            rm -rf $ODOO_ADDONS/\$rtname
            cp -r "\$rtdir" $ODOO_ADDONS/\$rtname
            chown -R odoo:odoo $ODOO_ADDONS/\$rtname
        fi
    done

    # Copy integrity manifest
    if [ -f /tmp/deploy_checksums.json ]; then
        mkdir -p /opt/vendor_license
        cp /tmp/deploy_checksums.json /opt/vendor_license/checksums.json
        chown root:odoo /opt/vendor_license/checksums.json
        chmod 640 /opt/vendor_license/checksums.json
    fi

    # Upgrade modules
    echo \"  Upgrading modules in Odoo...\"
    sudo -u odoo $ODOO_BIN -c $ODOO_CONF \
        -d ${ODOO_DB:-Payobook19} \
        -u $MOD_LIST \
        --stop-after-init --no-http 2>&1 | tail -3

    # Clean up temp files
    rm -rf /tmp/deploy_*

    # Restart Odoo
    service odoo-server restart
    echo \"  ✅ Odoo restarted\"
'"

echo
echo "═══════════════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo "═══════════════════════════════════════════════"
