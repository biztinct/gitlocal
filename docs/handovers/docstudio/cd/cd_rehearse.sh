#!/bin/bash
# DOCSTUDIO close-out D rehearsal on a hidden copy of ONE tenant (default rize; restored from the prep
# dump), jobs + mail servers off BEFORE anything else, dropped after. Goldens before and after the
# upgrade: phase F's letters (cd_golden_f.py) and phase A1's offers/certificates (cd_golden_a1.py) -
# English renders must be byte-identical; template rows may differ ONLY in the name of the two
# built-in offer letters (Z3). Then the probe with real PDFs (Z1, Z3, Z4, L).
# Clone of w2/w2_rehearse.sh. Root: bash cd_rehearse.sh <TS> [src]
TS=$1; SRC=${2:-rize}
EV=/tmp/cd-$TS
BK=/odoo/backups/docstudio-close-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployCD/addons
COPY=cd_rh_$SRC
MODS=$(cat /tmp/cd_mods.txt)
UPG=$(echo $MODS | tr ' ' ',')
IN=$(echo $MODS | sed "s/\([a-z_0-9]*\)/'\1'/g; s/ /,/g")
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal.done $EV/rehearsal.result
for kind in old new; do sed -e "s#^logfile.*#logfile = $EV/rh-$kind-odoo.log#" /etc/odoo-server.conf > $EV/$kind.conf; done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/new.conf
chown odoo:odoo $EV/old.conf $EV/new.conf; chmod 600 $EV/old.conf $EV/new.conf
cp /tmp/cd_probe.py /tmp/cd_golden_f.py /tmp/cd_golden_a1.py $EV/; chown odoo:odoo $EV/cd_probe.py $EV/cd_golden_f.py $EV/cd_golden_a1.py
sh_() { local kind=$1 script=$2 out=$3; sudo -u odoo PROBE_PDF=1 python3 /odoo/odoo-server/odoo-bin shell -c $EV/$kind.conf -d $COPY --no-http --max-cron-threads=0 < $EV/$script > $out 2>&1; }
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"      # hidden from the live job runner
sudo cat $BK/$SRC.dump | sudo -u postgres pg_restore -d $COPY > $EV/rh-restore-$SRC.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
   -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
E_SRC=$(pq -d $SRC -c "select count(*) from hr_employee"); E_COPY=$(pq -d $COPY -c "select count(*) from hr_employee")
log "[$SRC] copy restored; employees $E_COPY (live $E_SRC); jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active")"
if [ "$E_COPY" != "$E_SRC" ] || [ "$E_COPY" = 0 ]; then log "[$SRC] copy is not a real copy - stopping"; echo FAILED-COPY > $EV/rehearsal.result
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; touch $EV/rehearsal.done; exit 1; fi
rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
bash /tmp/cd_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
sh_ old cd_probe.py $EV/rh-$SRC-probe-old.out
log "[$SRC] old: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-old.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1500)"
for g in cd_golden_f cd_golden_a1; do sh_ old $g.py $EV/rh-$SRC-$g-before.txt; done
log "[$SRC] golden F before: $(grep -c '^GOLDEN' $EV/rh-$SRC-cd_golden_f-before.txt) line, $(grep '^GOLDEN' $EV/rh-$SRC-cd_golden_f-before.txt | grep -o 'ERROR' | wc -l) letter errors; golden A1 before: $(grep -c '^GOLDEN' $EV/rh-$SRC-cd_golden_a1-before.txt) lines, Traceback $(grep -c Traceback $EV/rh-$SRC-cd_golden_a1-before.txt)"
U0=$(date +%s)
rm -f $EV/rh-new-odoo.log
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/new.conf -d $COPY -u $UPG \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-new-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] upgrade exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(cat $EV/rh-$SRC-upgrade.log 2>/dev/null | grep -cE ' WARNING '), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /' | tee -a $EV/rehearsal.log
log "[$SRC] versions: $(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ($IN)")"
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); new job rows: $(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | paste -sd' ' -)"
bash /tmp/cd_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts before vs after (jobs and x_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-140 | tr '\n' ' ') || echo identical)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-260 | tr '\n' ' ')"
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
for g in cd_golden_f cd_golden_a1; do sh_ new $g.py $EV/rh-$SRC-$g-after.txt; done
log "[$SRC] golden F after vs before: $(python3 /tmp/cd_golden_cmp.py $EV/rh-$SRC-cd_golden_f-before.txt $EV/rh-$SRC-cd_golden_f-after.txt)"
diff <(grep '^GOLDEN' $EV/rh-$SRC-cd_golden_a1-before.txt) <(grep '^GOLDEN' $EV/rh-$SRC-cd_golden_a1-after.txt) > $EV/rh-$SRC-golden-a1-diff.txt
log "[$SRC] golden A1 after vs before: $([ -s $EV/rh-$SRC-golden-a1-diff.txt ] && echo "DIFFERENT in: $(grep '^>' $EV/rh-$SRC-golden-a1-diff.txt | sed -E 's/^> GOLDEN (.*) [^ ]+$/\1/' | tr '\n' ';')" || echo IDENTICAL) ($(grep -c '^GOLDEN' $EV/rh-$SRC-cd_golden_a1-after.txt) lines after, Traceback $(grep -c Traceback $EV/rh-$SRC-cd_golden_a1-after.txt))"
sh_ new cd_probe.py $EV/rh-$SRC-probe-new.out
log "[$SRC] new: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-new.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-2500)"
sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left"
rm -f $EV/old.conf $EV/new.conf
[ $UX = 0 ] && echo OK > $EV/rehearsal.result || echo FAILED > $EV/rehearsal.result
touch $EV/rehearsal.done
