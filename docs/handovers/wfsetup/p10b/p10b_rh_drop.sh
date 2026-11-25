#!/bin/bash
# WFSETUP P10b: drop the hidden copy, its file folder and the private code dir. Root: bash p10b_rh_drop.sh <copy>
COPY=$1; FS=/odoo/.local/share/Odoo/filestore
case "$COPY" in zz_wfs_p10b_*) ;; *) echo "copy only"; exit 1;; esac
sudo -u postgres psql -X -At -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false" && sudo -u postgres dropdb --force $COPY
rm -rf $FS/$COPY /tmp/p10b_rh
echo "left: $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'zz_wfs_p10b_%'") copies"
