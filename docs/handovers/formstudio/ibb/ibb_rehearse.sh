#!/bin/bash
# INBOX-BULK-BANK rehearsal on hidden copies of the five databases (the LIVE installed module set:
# restored from the prep dumps), jobs + mail off, dropped after. Clone of fs13/fs13_rehearse.sh.
# Every copy: upgrade timed, counts restored vs upgraded, probe (counts + pages) old vs new.
# rize: payslips old vs new code. sudima: as the approver's seat (IBB_UID) approve ALL waiting
# bank-detail requests (select all, the check, groups of 50), counts and joining checklist before
# and after, payslips before vs after the approvals.
# Root: bash ibb_rehearse.sh <TS> [srcdbs]
TS=$1
SRCS=${2:-"sudima rize p0clone payobook payobook_template"}
EV=/tmp/ibb-$TS
BK=/odoo/backups/ibb-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployIBB/addons
UPD=biz_approval_workflow,pb_approval_config,pb_employee_bank_panel
IBB_UID=${IBB_UID:-2500}
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal.done
for kind in old new; do
  sed -e "s#^logfile.*#logfile = $EV/rh-$kind-odoo.log#" /etc/odoo-server.conf > $EV/$kind.conf
done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/new.conf
chown odoo:odoo $EV/old.conf $EV/new.conf; chmod 600 $EV/old.conf $EV/new.conf
cp /tmp/te_recompute.py /tmp/ibb_probe.py $EV/; chown odoo:odoo $EV/*.py
for SRC in $SRCS; do
  COPY=ibb_rh_$SRC
  sh_() {  # kind outfile [env...] < script
    local kind=$1 out=$2; shift 2
    sudo -u odoo env PROBE_HOST=$COPY.payobook.com "$@" python3 /odoo/odoo-server/odoo-bin shell -c $EV/$kind.conf -d $COPY --no-http --max-cron-threads=0 > $out 2>&1
  }
  if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
    pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
  fi
  sudo -u postgres createdb -O odoo $COPY
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"      # hidden from the live job runner
  DUMP=$BK/$SRC.dump
  # the 358 were approved on live (23:43 UTC, another session, owner's instruction) before this
  # phase went live: test 8 runs on the dump taken just before that, which still has them waiting
  [ $SRC = sudima ] && [ -n "$SUDIMA_DUMP" ] && DUMP=$SUDIMA_DUMP
  log "[$SRC] restoring $DUMP"
  sudo -u postgres pg_restore -d $COPY < $DUMP > $EV/rh-restore-$SRC.log 2>&1
  pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
     -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
  log "[$SRC] copy restored; jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active")"
  rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
  bash /tmp/ibb_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"     # the web stack lists no template
  for mode in counts pages; do
    sh_ old $EV/rh-$SRC-$mode-old.out IBB_MODE=$mode < $EV/ibb_probe.py
    log "[$SRC] $mode old: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-$mode-old.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1200)"
  done
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  if [ $SRC = rize ]; then
    RUNS=$(pq -d $COPY -c "select string_agg(id::text, ',' order by id desc) from (select id from hr_payslip_run order by id desc limit 4) x")
    log "[$SRC] runs recomputed: $RUNS"
    sh_ old $EV/rc-old.out RC_OUT=$EV/rc-old.json RUN_IDS=$RUNS < $EV/te_recompute.py
    log "[$SRC] old recompute: $(grep -E '^RC runs|Traceback' $EV/rc-old.out | head -2)"
  fi
  U0=$(date +%s)
  rm -f $EV/rh-new-odoo.log
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/new.conf -d $COPY -u $UPD --stop-after-init \
    --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
  UX=$?
  cp $EV/rh-new-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
  log "[$SRC] upgrade exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
  grep -hE ' (ERROR|CRITICAL) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | head -5 | sed 's/^/    /' | tee -a $EV/rehearsal.log
  log "[$SRC] one-time step: $(grep -h 'extra confirmation switched on' $EV/rh-$SRC-upgrade.log | sed 's/.*INFO [^ ]* [^ ]* //' | head -1)"
  log "[$SRC] versions: $(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('biz_approval_workflow','pb_approval_config','pb_employee_bank_panel')")"
  log "[$SRC] jobs active after upgrade: $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron") (all were off)"
  bash /tmp/ibb_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
  diff <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
  log "[$SRC] counts restored vs upgraded (jobs and the new column excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep '^>' $EV/rh-$SRC-diff-01.txt | cut -c1-90 | tr '\n' ' ') || echo identical); $(grep '^x_' $EV/rh-$SRC-counts-1.txt)"
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  for mode in counts pages; do
    sh_ new $EV/rh-$SRC-$mode-new.out IBB_MODE=$mode < $EV/ibb_probe.py
    log "[$SRC] $mode new: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-$mode-new.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1500)"
  done
  diff <(grep -E '^PROBE pages emp' $EV/rh-$SRC-pages-old.out) <(grep -E '^PROBE pages emp' $EV/rh-$SRC-pages-new.out) > $EV/rh-$SRC-pages.diff
  log "[$SRC] /my and My Leave old vs new ($(grep -c '^PROBE pages emp' $EV/rh-$SRC-pages-old.out) people): $([ -s $EV/rh-$SRC-pages.diff ] && echo DIFFERENT || echo byte-identical)"
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  if [ $SRC = rize ]; then
    sh_ new $EV/rc-new.out RC_OUT=$EV/rc-new.json RUN_IDS=$RUNS < $EV/te_recompute.py
    python3 -I /tmp/te_compare_rc.py $EV/rc-old.json $EV/rc-new.json > $EV/rc-compare.txt 2>&1
    log "[$SRC] payslips old vs new: $(tail -1 $EV/rc-compare.txt)"
  fi
  if [ $SRC = sudima ]; then
    sh_ new $EV/sd-rc-before.out RC_OUT=$EV/sd-rc-before.json MAX_SLIPS=3 < $EV/te_recompute.py
    log "[$SRC] payslips before the approvals: $(grep -E '^RC runs|Traceback' $EV/sd-rc-before.out | head -2)"
    A0=$(date +%s)
    sh_ new $EV/sd-approve.out IBB_MODE=approve IBB_UID=$IBB_UID < $EV/ibb_probe.py
    log "[$SRC] approve ALL as seat $IBB_UID ($(( $(date +%s) - A0 )) s): $(grep -E '^PROBE|Traceback|Error' $EV/sd-approve.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-3000)"
    sh_ new $EV/sd-rc-after.out RC_OUT=$EV/sd-rc-after.json MAX_SLIPS=3 < $EV/te_recompute.py
    python3 -I /tmp/te_compare_rc.py $EV/sd-rc-before.json $EV/sd-rc-after.json > $EV/sd-rc-compare.txt 2>&1
    log "[$SRC] payslips before vs after the approvals: $(tail -1 $EV/sd-rc-compare.txt)"
    bash /tmp/ibb_counts.sh $COPY > $EV/rh-$SRC-counts-2.txt
    log "[$SRC] counts after the approvals: $(diff $EV/rh-$SRC-counts-1.txt $EV/rh-$SRC-counts-2.txt | grep '^>' | cut -c1-60 | tr '\n' ' ')"
  fi
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'")"
done
rm -f $EV/old.conf $EV/new.conf
touch $EV/rehearsal.done
