#!/bin/bash
# FS-16 rehearsal follow-up on ONE hidden copy (jobs + mail off, dropped after): which chatter messages appear
# (after the probe's page visits, after the upgrade) and how the employee form differs old vs new.
# Root: bash fs16_investigate.sh <TS> <SRC>
TS=$1; SRC=${2:-rize}
EV=/tmp/fs16-$TS
BK=/odoo/backups/fs16-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployFS16/addons
UPD=pb_hr_payroll_vietnam,pb_employee_form_tidy,pb_form_studio_people,pb_people_advanced,pb_bank_ocr,pb_employee_bank_panel
COPY=fs16_inv_$SRC
OUT=$EV/inv-$SRC
log() { echo "$(date -u +%T) $*" | tee -a $OUT.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
for kind in old new; do sed -e "s#^logfile.*#logfile = $EV/inv-$kind-odoo.log#" /etc/odoo-server.conf > $EV/inv-$kind.conf; done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/inv-new.conf
chown odoo:odoo $EV/inv-*.conf; chmod 600 $EV/inv-*.conf
cp /tmp/fs16_formdump.py /tmp/fs16_probe.py $EV/ && chown odoo:odoo $EV/fs16_formdump.py $EV/fs16_probe.py
sh_() { local kind=$1 out=$2; shift 2; sudo -u odoo env PROBE_HOST=$COPY.payobook.com "$@" python3 /odoo/odoo-server/odoo-bin shell -c $EV/inv-$kind.conf -d $COPY --no-http --max-cron-threads=0 > $out 2>&1; }
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
sudo -u postgres pg_restore -d $COPY < $BK/$SRC.dump > $OUT-restore.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false"
rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
M0=$(pq -d $COPY -c "select max(id) from mail_message")
sh_ old $OUT-form-old.out FORM_OUT=$OUT-form-old.xml MSG_AFTER=$M0 < $EV/fs16_formdump.py
sh_ old $OUT-probe-old.out < $EV/fs16_probe.py
M1=$(pq -d $COPY -c "select max(id) from mail_message")
log "messages after the old probe (page visits): $((M1 - M0))"
sh_ old $OUT-msg1.out MSG_AFTER=$M0 FORM_OUT=/dev/null < $EV/fs16_formdump.py; grep '^MSG ' $OUT-msg1.out | tee -a $OUT.log
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/inv-new.conf -d $COPY -u $UPD --stop-after-init --no-http --max-cron-threads=0 > $OUT-upgrade.out 2>&1
log "upgrade exit $?"
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
M2=$(pq -d $COPY -c "select max(id) from mail_message")
log "messages made by the upgrade: $((M2 - M1))"
sh_ new $OUT-msg2.out MSG_AFTER=$M1 FORM_OUT=$OUT-form-new.xml < $EV/fs16_formdump.py; grep '^MSG ' $OUT-msg2.out | tee -a $OUT.log
diff $OUT-form-old.xml $OUT-form-new.xml > $OUT-form.diff
log "form diff lines: $(grep -c '^[<>]' $OUT-form.diff)"
head -60 $OUT-form.diff | cut -c1-220 | tee -a $OUT.log
sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
rm -f $EV/inv-old.conf $EV/inv-new.conf
log "copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'")"
touch $OUT.done
