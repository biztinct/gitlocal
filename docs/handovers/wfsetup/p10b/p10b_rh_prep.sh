#!/bin/bash
# WFSETUP P10b rehearsal prep (clone of ../p8/p8_prep.sh): dump LIVE sudima (read-only), restore it as the
# hidden copy zz_wfs_p10b_<date> (TEMPLATE database: the live job runner and web front never list it, WS45),
# every job, mail server and incoming mail server OFF before anything else. Two private confs:
#   old.conf  the live addons dir (today's code)  - for the "before" neutrality probe
#   new.conf  /tmp/p10b_rh/addons FIRST (the seven P10b modules from the pushed commit), then the live
#             addons dir - used ONLY by this copy's own odoo-bin processes; the live service and its
#             conf are untouched (one addons dir on live, CLAUDE.md)
# Root: bash p10b_rh_prep.sh <TS> <copy-name>
set -u
TS=$1; COPY=$2
EV=/tmp/wfsetup-p10b-$TS
BK=/odoo/backups/wfsetup-p10b-$TS
FS=/odoo/.local/share/Odoo/filestore
case "$COPY" in zz_wfs_p10b_*) ;; *) echo "copy name must start zz_wfs_p10b_"; exit 1;; esac
mkdir -p $EV $BK; chmod 700 $BK
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
sudo -u postgres pg_dump -Fc -d sudima > $BK/sudima-before-rehearsal.dump
[ -s $BK/sudima-before-rehearsal.dump ] || { log "dump FAILED - stopping"; exit 1; }
log "dump of live sudima: $(stat -c %s $BK/sudima-before-rehearsal.dump) bytes -> $BK"
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
cat $BK/sudima-before-rehearsal.dump | sudo -u postgres pg_restore -d $COPY > $EV/restore.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
   -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
log "copy $COPY restored (template); jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active"); employees $(pq -d $COPY -c "select count(*) from hr_employee")"
rm -rf $FS/$COPY; cp -al $FS/sudima $FS/$COPY; chown -R odoo:odoo $FS/$COPY
rm -rf /tmp/p10b_rh && mkdir -p /tmp/p10b_rh/addons && tar -xf /tmp/p10b_stage.tar -C /tmp/p10b_rh/addons && chown -R odoo:odoo /tmp/p10b_rh
sed -e "s#^logfile.*#logfile = $EV/copy-odoo.log#" /etc/odoo-server.conf > $EV/old.conf
sed -e "s#^logfile.*#logfile = $EV/copy-odoo.log#" -e "s#^addons_path *=.*#addons_path = /tmp/p10b_rh/addons,/odoo/odoo-server/addons#" /etc/odoo-server.conf > $EV/new.conf
grep -q '^addons_path = /tmp/p10b_rh/addons' $EV/new.conf || { log "new.conf has no addons_path line - stopping"; exit 1; }
chown odoo:odoo $EV/old.conf $EV/new.conf; chmod 600 $EV/old.conf $EV/new.conf; chown -R odoo:odoo $EV
log "copy ready: $EV/old.conf (live code) $EV/new.conf (P10b code first)"
