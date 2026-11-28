#!/bin/bash
# NEWHIRE P8: stop the rehearsal service, drop ONE rehearsal copy, its file folder and the private
# confs / password file. Clone of ../p5b/nh_rh_drop.sh. Root: bash nh8_rh_drop.sh <TS> <src>
TS=$1; SRC=$2
EV=/tmp/newhire-p8-$TS
COPY=nh8_rh_$SRC
FS=/odoo/.local/share/Odoo/filestore
case "$COPY" in nh8_rh_rize|nh8_rh_payobook) ;; *) echo "copy only"; exit 1;; esac
systemctl stop nh8-rh-serve 2>/dev/null; systemctl reset-failed nh8-rh-serve 2>/dev/null
sudo -u postgres psql -X -At -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false" 2>/dev/null
sudo -u postgres dropdb --force --if-exists $COPY
rm -rf $FS/$COPY
rm -f $EV/rh-$SRC.conf $EV/rh-serve.conf $EV/rh-tests.conf $EV/rh-login-$SRC.txt
echo "$(date -u +%T) [$SRC] dropped: copies left $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'nh8_rh%'"), file folder $( [ -e $FS/$COPY ] && echo LEFT || echo gone), service $(systemctl is-active nh8-rh-serve 2>/dev/null), login file $( [ -e $EV/rh-login-$SRC.txt ] && echo LEFT || echo gone)" | tee -a $EV/rehearsal.log
