#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Build Release — Obfuscate Python + Minify JS/CSS
#
# This script prepares deployment-ready modules with:
# 1. PyArmor obfuscation (RFT + BCC) for all Python files
# 2. Terser minification for JS files
# 3. CSSNano minification for CSS files
# 4. SHA-256 integrity manifest generation
#
# Prerequisites:
#   pip install pyarmor
#   npm install -g terser cssnano-cli
#
# Usage:
#   ./build_release.sh [output_dir] [--plain]
#   ./build_release.sh                    # → obfuscated to ./dist/
#   ./build_release.sh /tmp/build         # → obfuscated to /tmp/build/
#   ./build_release.sh --plain            # → plain (un-obfuscated) to ./dist/
#   ./build_release.sh /tmp/build --plain # → plain to /tmp/build/
#
# Performance Notes:
#   PyArmor with --enable-bcc compiles Python to C extensions.
#   This is actually FASTER than plain Python at runtime.
#   RFT renames variables (5-10% overhead max).
#   Odoo bottleneck is PostgreSQL, not Python — no noticeable impact.
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/.."  # gitlocal root

# Parse arguments
OUTPUT_DIR=""
PLAIN_MODE=false

for arg in "$@"; do
    case "$arg" in
        --plain)
            PLAIN_MODE=true
            ;;
        *)
            OUTPUT_DIR="$arg"
            ;;
    esac
done

OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_ROOT/dist}"

# Modules to protect
PROTECTED_MODULES=(
    vendor_license_core
    pb_hr_payroll_formula
    om_hr_payroll
    pb_hr_payroll_base
    pb_hr_workforce
    pb_hr_flow
    pb_hr_payroll_analytics
    pb_hr_govt
    payroll_analytics_approval
)

echo "═══════════════════════════════════════════════"
if $PLAIN_MODE; then
    echo "  Building Release (PLAIN MODE — no obfuscation)"
else
    echo "  Building Release (OBFUSCATED — PyArmor RFT+BCC)"
fi
echo "  Output: $OUTPUT_DIR"
echo "═══════════════════════════════════════════════"
echo

# Clean
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# ── Step 1: Copy / Obfuscate Python ──
if $PLAIN_MODE; then
    echo "── Step 1: Copying modules (plain mode) ──"
    for mod in "${PROTECTED_MODULES[@]}"; do
        if [ -d "$mod" ]; then
            echo "  Copying $mod..."
            cp -r "$mod" "$OUTPUT_DIR/$mod"
            # Remove .bak and dev artifacts
            find "$OUTPUT_DIR/$mod" -name "*.bak" -delete 2>/dev/null || true
            find "$OUTPUT_DIR/$mod" -name "*.i18n_bak" -delete 2>/dev/null || true
            find "$OUTPUT_DIR/$mod" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        else
            echo "  ⚠️  Module $mod not found, skipping"
        fi
    done
else
    echo "── Step 1: PyArmor Obfuscation (RFT + BCC) ──"
    for mod in "${PROTECTED_MODULES[@]}"; do
        if [ -d "$mod" ]; then
            echo "  Obfuscating $mod..."
            pyarmor gen \
                --enable-rft \
                --enable-bcc \
                --platform linux.x86_64 \
                --output "$OUTPUT_DIR" \
                "$mod/" 2>/dev/null || {
                    echo "  ⚠️  PyArmor BCC failed for $mod, trying RFT-only..."
                    pyarmor gen \
                        --enable-rft \
                        --platform linux.x86_64 \
                        --output "$OUTPUT_DIR" \
                        "$mod/" 2>/dev/null || {
                            echo "  ⚠️  PyArmor RFT failed, trying BASIC mode..."
                            pyarmor gen \
                                --platform linux.x86_64 \
                                --output "$OUTPUT_DIR" \
                                "$mod/" 2>/dev/null || {
                                    echo "  ⚠️  PyArmor failed entirely for $mod, copying plain"
                                    cp -r "$mod" "$OUTPUT_DIR/"
                                }
                        }
                }
        else
            echo "  ⚠️  Module $mod not found, skipping"
        fi
    done
fi
echo

# ── Step 2: JS Minification ──
echo "── Step 2: JS Minification ──"
if command -v terser &> /dev/null; then
    JS_COUNT=0
    find "$OUTPUT_DIR" -name "*.js" -path "*/static/src/js/*" | while read -r jsfile; do
        echo "  Minifying $(basename "$jsfile")..."
        terser "$jsfile" --compress --mangle -o "$jsfile" 2>/dev/null || true
        JS_COUNT=$((JS_COUNT + 1))
    done
    echo "  Done"
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
    echo "  Done"
else
    echo "  ⚠️  cssnano not found, skipping CSS minification"
    echo "  Install with: npm install -g cssnano-cli"
fi
echo

# ── Step 4: Strip vendor-only tools/ directory ──
echo "── Step 4: Removing vendor-only files ──"
rm -rf "$OUTPUT_DIR/vendor_license_core/tools"
echo "  Removed tools/ from vendor_license_core"
echo

# ── Step 5: Generate Integrity Manifest ──
echo "── Step 5: Generating Integrity Manifest ──"
MANIFEST_PATH="$OUTPUT_DIR/checksums.json"
python3 -c "
import hashlib, json, os

manifest = {}
base = '$OUTPUT_DIR'
modules = '$( IFS=,; echo "${PROTECTED_MODULES[*]}" )'.split(',')

for mod in modules:
    mod = mod.strip()
    mod_path = os.path.join(base, mod)
    if not os.path.isdir(mod_path):
        continue
    for root, dirs, files in os.walk(mod_path):
        dirs[:] = [d for d in dirs if not d.startswith(('.', '__pycache__'))]
        for f in files:
            if f.endswith(('.py', '.pyc', '.pyd', '.so')):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, base)
                h = hashlib.sha256(open(fp, 'rb').read()).hexdigest()
                manifest[rel] = h

with open('$MANIFEST_PATH', 'w') as f:
    json.dump(manifest, f, indent=2, sort_keys=True)

print(f'  Manifest: {len(manifest)} files checksummed → checksums.json')
" 2>/dev/null || echo "  ⚠️  Manifest generation failed (Python not found?)"
echo

# ── Done ──
echo "═══════════════════════════════════════════════"
echo "  ✅ Build Complete!"
echo "  Output: $OUTPUT_DIR"
echo ""
echo "  Next steps:"
echo "  1. Copy $OUTPUT_DIR/* to client's Odoo addons directory"
echo "  2. Copy $OUTPUT_DIR/checksums.json to /opt/vendor_license/"
echo "  3. Ensure /opt/vendor_license/license.json is in place"
echo "  4. Restart Odoo"
if $PLAIN_MODE; then
    echo ""
    echo "  ⚠️  PLAIN MODE — Python files are NOT obfuscated!"
    echo "  Use without --plain for production deployments."
fi
echo "═══════════════════════════════════════════════"
