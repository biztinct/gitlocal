#!/bin/bash
# WFSETUP P8 step A: dump LIVE sudima (read-only), restore it as the hidden copy zz_wfs_p8_<date>, switch
# every scheduled job, mail server and incoming mail server OFF on the copy before anything else, and
# keep the copy a TEMPLATE database (the live job runner and the web front never list it, ledger WS45).
# Clone of p5b/wfs_rehearse.sh (restore part). Root: bash p8_prep.sh <TS> <copy-name>
set -u
TS=$1; COPY=$2
EV=/tmp/wfsetup-p8-$TS
BK=/odoo/backups/wfsetup-p8-$TS
FS=/odoo/.local/share/Odoo/filestore
case "$COPY" in zz_wfs_p8_*) ;; *) echo "copy name must start zz_wfs_p8_"; exit 1;; esac
mkdir -p $EV $BK; chmod 700 $BK
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
sudo -u postgres pg_dump -Fc -d sudima > $BK/sudima-before-rehearsal.dump   # root writes the root-only folder
[ -s $BK/sudima-before-rehearsal.dump ] || { log "dump FAILED - stopping"; exit 1; }
log "dump of live sudima: $(stat -c %s $BK/sudima-before-rehearsal.dump) bytes -> $BK"
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
cat $BK/sudima-before-rehearsal.dump | sudo -u postgres pg_restore -d $COPY > $EV/restore.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
   -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
log "copy $COPY restored (template); jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active"); employees $(pq -d $COPY -c "select count(*) from hr_employee") (live $(pq -d sudima -c "select count(*) from hr_employee")); events $(pq -d $COPY -c "select count(*)||' '||string_agg(distinct state, ',') from pb_clock_connector_event")"
rm -rf $FS/$COPY; cp -al $FS/sudima $FS/$COPY; chown -R odoo:odoo $FS/$COPY
# private conf: live addons dir (code is identical), own log file, no jobs
sed -e "s#^logfile.*#logfile = $EV/copy-odoo.log#" /etc/odoo-server.conf > $EV/copy.conf
chown odoo:odoo $EV/copy.conf; chmod 600 $EV/copy.conf; chown -R odoo:odoo $EV
log "copy ready: conf $EV/copy.conf"
