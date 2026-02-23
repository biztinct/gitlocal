#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Build Release — Obfuscate Python + Minify JS/CSS
#
# This script prepares deployment-ready modules with:
# 1. PyArmor obfuscation for all Python files
# 2. Terser minification for JS files
# 3. CSSNano minification for CSS files
#
# Prerequisites:
#   pip install pyarmor
#   npm install -g terser cssnano-cli
#
# Usage:
#   ./build_release.sh [output_dir]
#   ./build_release.sh             # → outputs to ./dist/
#   ./build_release.sh /tmp/build  # → outputs to /tmp/build/
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/.."  # gitlocal root

OUTPUT_DIR="${1:-$PROJECT_ROOT/dist}"

# Modules to obfuscate
PROTECTED_MODULES=(
    vendor_license_core
    pb_hr_workforce
    pb_hr_flow
    om_hr_payroll
    pb_hr_payroll_vietnam
    pb_hr_payroll_formula
    pb_hr_govt
    payroll_analytics_approval
)

echo "═══════════════════════════════════════════════"
echo "  Building Release"
echo "  Output: $OUTPUT_DIR"
echo "═══════════════════════════════════════════════"
echo

# Clean
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# ── Step 1: PyArmor Obfuscation ──
echo "── Step 1: PyArmor Obfuscation ──"
for mod in "${PROTECTED_MODULES[@]}"; do
    if [ -d "$mod" ]; then
        echo "  Obfuscating $mod..."
        pyarmor gen \
            --enable-rft \
            --platform linux.x86_64 \
            --output "$OUTPUT_DIR/$mod" \
            "$mod/" 2>/dev/null || {
                echo "  ⚠️  PyArmor failed for $mod, copying plain instead"
                cp -r "$mod" "$OUTPUT_DIR/$mod"
            }
    else
        echo "  ⚠️  Module $mod not found, skipping"
    fi
done
echo

# ── Step 2: JS Minification ──
echo "── Step 2: JS Minification ──"
if command -v terser &> /dev/null; then
    find "$OUTPUT_DIR" -name "*.js" -path "*/static/src/js/*" | while read -r jsfile; do
        echo "  Minifying $(basename "$jsfile")..."
        terser "$jsfile" --compress --mangle -o "$jsfile" 2>/dev/null || true
    done
else
    echo "  ⚠️  terser not found, skipping JS minification"
    echo "  Install with: npm install -g terser"
fi
echo

# ── Step 3: CSS Minification ──
echo "── Step 3: CSS Minification ──"
if command -v cssnano &> /dev/null; then
    find "$OUTPUT_DIR" -name "*.css" -path "*/static/src/css/*" | while read -r cssfile; do
        echo "  Minifying $(basename "$cssfile")..."
        cssnano "$cssfile" "$cssfile" 2>/dev/null || true
    done
else
    echo "  ⚠️  cssnano not found, skipping CSS minification"
    echo "  Install with: npm install -g cssnano-cli"
fi
echo

# ── Step 4: Strip tools/ directory (vendor-only) ──
echo "── Step 4: Removing vendor-only files ──"
rm -rf "$OUTPUT_DIR/vendor_license_core/tools"
echo "  Removed tools/ from vendor_license_core"
echo

# ── Done ──
echo "═══════════════════════════════════════════════"
echo "  ✅ Build Complete!"
echo "  Output: $OUTPUT_DIR"
echo ""
echo "  Next steps:"
echo "  1. Copy $OUTPUT_DIR/* to client's Odoo addons directory"
echo "  2. Ensure /opt/vendor_license/license.json is in place"
echo "  3. Restart Odoo"
echo "═══════════════════════════════════════════════"
