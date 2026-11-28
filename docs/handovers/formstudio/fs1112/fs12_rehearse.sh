#!/bin/bash
# FS-11/FS-12 rehearsal on hidden copies (jobs + mail off; dropped after). Root: bash fs12_rehearse.sh <TS> [srcdbs]
# every copy: upgrade with the staged code, counts restored vs upgraded, probes, the P6c mark log line;
# rize: payslips old vs new (last 4 runs) + Studio suite (rolled back) + Access abilities (G80);
# p0clone: Studio suite.
TS=$1
SRCS=${2:-"rize p0clone sudima payobook payobook_template"}
EV=/tmp/fs12-$TS
BK=/odoo/backups/fs12-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployFS12/addons
UPD=pb_form_studio,pb_form_studio_people,pb_form_studio_contracts
INS=pb_form_studio_portal
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal.done
for kind in old new; do
  sed -e "s#^logfile.*#logfile = $EV/rh-$kind-odoo.log#" /etc/odoo-server.conf > $EV/$kind.conf
done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/new.conf
chown odoo:odoo $EV/old.conf $EV/new.conf; chmod 600 $EV/old.conf $EV/new.conf
cp /tmp/te_recompute.py /tmp/fs12_probe.py /tmp/fs12_publish.py $EV/; chown odoo:odoo $EV/*.py
for SRC in $SRCS; do
  COPY=fs12_rh_$SRC
  sh_() {  # kind outfile [env...] < script
    local kind=$1 out=$2; shift 2
    sudo -u odoo env PROBE_HOST=$COPY.payobook.com "$@" python3 /odoo/odoo-server/odoo-bin shell -c $EV/$kind.conf -d $COPY --no-http --max-cron-threads=0 > $out 2>&1
  }
  if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
    pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
  fi
  sudo -u postgres createdb -O odoo $COPY
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"      # hidden from the live job runner
  sudo -u postgres pg_restore -d $COPY < $BK/$SRC.dump > $EV/rh-restore-$SRC.log 2>&1
  pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
     -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
  log "[$SRC] copy restored; jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active")"
  rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
  bash /tmp/fs12_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"     # the web stack lists no template
  sh_ old $EV/rh-$SRC-probe-old.out < $EV/fs12_probe.py
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  log "[$SRC] old: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-old.out | sed 's/^PROBE //' | tr '\n' ';')"
  if [ $SRC = rize ]; then
    RUNS=$(pq -d $COPY -c "select string_agg(id::text, ',' order by id desc) from (select id from hr_payslip_run order by id desc limit 4) x")
    log "[$SRC] runs recomputed: $RUNS"
    sh_ old $EV/rc-old.out RC_OUT=$EV/rc-old.json RUN_IDS=$RUNS < $EV/te_recompute.py
    log "[$SRC] old recompute: $(grep -E '^RC runs|Traceback' $EV/rc-old.out | head -2)"
  fi
  U0=$(date +%s)
  rm -f $EV/rh-new-odoo.log
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/new.conf -d $COPY -u $UPD -i $INS --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
  UX=$?
  cp $EV/rh-new-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
  log "[$SRC] upgrade exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(grep -cE ' (ERROR|CRITICAL) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out | awk -F: '{s+=$2} END {print s}'), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
  grep -hE ' (ERROR|CRITICAL) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | head -5 | sed 's/^/    /' | tee -a $EV/rehearsal.log
  log "[$SRC] versions: $(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_form_studio','pb_form_studio_people','pb_form_studio_contracts','pb_form_studio_portal')")"
  log "[$SRC] jobs active after upgrade: $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron") (all were off)"
  bash /tmp/fs12_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
  diff <(grep -vE '^(jobs_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
  log "[$SRC] counts restored vs upgraded (jobs excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep '^>' $EV/rh-$SRC-diff-01.txt | cut -c1-90 | tr '\n' ' ') || echo identical)"
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sh_ new $EV/rh-$SRC-probe-new.out < $EV/fs12_probe.py
  log "[$SRC] new: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-new.out | sed 's/^PROBE //' | tr '\n' ';')"
  diff <(grep -E '^PROBE page emp' $EV/rh-$SRC-probe-old.out | sed -E 's#/my [0-9]+ [0-9a-f]+ \| ##') \
       <(grep -E '^PROBE page emp' $EV/rh-$SRC-probe-new.out | sed -E 's#/my [0-9]+ [0-9a-f]+ \| ##') > $EV/rh-$SRC-pages.diff
  log "[$SRC] employee pages old vs new (My Profile, My details, My Leave): $([ -s $EV/rh-$SRC-pages.diff ] && echo DIFFERENT || echo byte-identical)"
  if [ $SRC = rize ] || [ $SRC = payobook ]; then
    sh_ new $EV/rh-$SRC-publish.out < $EV/fs12_publish.py
    log "[$SRC] page published on the copy: $(grep -E '^PUB|Traceback' $EV/rh-$SRC-publish.out | tr '\n' ';')"
    sh_ new $EV/rh-$SRC-probe-page.out < $EV/fs12_probe.py
    log "[$SRC] with a page: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-page.out | sed 's/^PROBE //' | tr '\n' ';')"
  fi
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  if [ $SRC = rize ]; then
    sh_ new $EV/rc-new.out RC_OUT=$EV/rc-new.json RUN_IDS=$RUNS < $EV/te_recompute.py
    python3 -I /tmp/te_compare_rc.py $EV/rc-old.json $EV/rc-new.json > $EV/rc-compare.txt 2>&1
    log "[$SRC] payslips old vs new: $(tail -1 $EV/rc-compare.txt)"
  fi
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'")"
done
rm -f $EV/old.conf $EV/new.conf
touch $EV/rehearsal.done
