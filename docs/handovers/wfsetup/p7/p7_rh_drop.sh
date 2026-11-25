#!/bin/bash
# WFSETUP P7: stop the rehearsal service, drop the rehearsal copy, its file folder and the private
# confs / password file. Clone of ../p5b/wfs_rh_drop.sh. Root: bash p7_rh_drop.sh <TS> [src]
TS=$1; SRC=${2:-rize}
EV=/tmp/wfsetup-p7-$TS
COPY=wfs_rh7_$SRC
FS=/odoo/.local/share/Odoo/filestore
systemctl stop wfs-rh7-serve 2>/dev/null; systemctl reset-failed wfs-rh7-serve 2>/dev/null
sudo -u postgres psql -X -At -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false" 2>/dev/null
sudo -u postgres dropdb --force --if-exists $COPY
rm -rf $FS/$COPY
rm -f $EV/rh-*.conf $EV/rh-serve.conf $EV/rh-login.txt
echo "$(date -u +%T) [$SRC] dropped: copies left $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'wfs_rh7%'"), file folder $( [ -e $FS/$COPY ] && echo LEFT || echo gone), service $(systemctl is-active wfs-rh7-serve 2>/dev/null), login file $( [ -e $EV/rh-login.txt ] && echo LEFT || echo gone)" | tee -a $EV/rehearsal.log
