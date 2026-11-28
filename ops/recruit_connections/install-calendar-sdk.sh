#!/bin/bash
# Run as root on Payobook19v2 after staging the resolved dependency directory.
# No global Python packages or standard Odoo addons are changed.
set -euo pipefail
source_dir=${1:?Supply the rehearsed SDK directory}
target_dir=/odoo/vendor/hiring-calendar-sdk
mkdir -p "$target_dir"
rsync -a --delete "$source_dir/" "$target_dir/"
chown -R root:root "$target_dir"
chmod -R a+rX "$target_dir"
