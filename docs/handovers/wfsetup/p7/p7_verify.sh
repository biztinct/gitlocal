#!/bin/bash
# WFSETUP P7 verification after the go-live (read-only). Clone of ../p6/p6_verify.sh + ../p5b/wfs_verify.sh:
# trees, versions x5 (setup + rules module now on all five), jobs, template job list, data before vs
# installed, compiled code, server log, sites. Root: bash p7_verify.sh <TS>
TS=$1
EV=/tmp/wfsetup-p7-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook_template p0clone rize"
ALLDBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/p7_mods.txt)
pq() { sudo -u postgres psql -X -At -d "$@"; }
{
echo "== trees"
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt /tmp/p7_commit_trees.txt && echo "all $(wc -l < $EV/live-trees-verify.txt) trees = commit $(cat /tmp/p7_commit.txt)"
echo "== versions (manifest vs latest_version)"
for m in pb_workforce_setup pb_attendance_policy pb_workforce_workspace pb_hr_workforce; do
  v=$(grep "^$m " /tmp/p7_commit_trees.txt | awk '{print $2}')
  echo "$m manifest $v: $(for db in $ALLDBS; do st=$(pq $db -c "select state||':'||coalesce(latest_version,'') from ir_module_module where name='$m'"); [ "$st" = "installed:$v" ] && echo -n "$db ok; " || echo -n "$db MISMATCH($st); "; done)"
done
echo "== every installed custom module of the closure: manifest = latest_version"
for db in $ALLDBS; do
  bad=""; while read -r m v h; do st=$(pq $db -c "select state||':'||coalesce(latest_version,'') from ir_module_module where name='$m'")
    case "$st" in "installed:$v"|"installed:19.0.$v") ;; *) bad="$bad $m($st vs $v)";; esac; done < /tmp/p7_commit_trees.txt
  echo "$db: ${bad:-all $(wc -l < /tmp/p7_commit_trees.txt) ok}"
done
echo "== jobs (prep snapshot -> now)"
for db in $ALLDBS; do
  pq $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  NEWIDS=$(join -t, -v2 <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | cut -d, -f1 | paste -sd, -)
  echo "$db: total $(wc -l < $EV/cron-before-$db.txt) -> $(wc -l < $EV/cron-after-$db.txt), active $(grep -c ',true$' $EV/cron-before-$db.txt) -> $(grep -c ',true$' $EV/cron-after-$db.txt); changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')$([ -n "$NEWIDS" ] && echo " = $(pq $db -c "select string_agg(id||' '||(cron_name->>'en_US')||' every '||interval_number||' '||interval_type||' active='||active::text, '; ') from ir_cron where id in ($NEWIDS)" 2>&1)")"
done
echo "payobook job 156: $(pq payobook -c "select active from ir_cron where id=156")"
echo "payobook_template recorded job list: before $(tr ',' '\n' < $EV/template-active-crons-before.txt | grep -c .) ids, now $(pq payobook_template -c "select value from ir_config_parameter where key='pb_tenants.template_active_crons'" | tr ',' '\n' | grep -c .) ids; added: $(comm -13 <(tr ',' '\n' < $EV/template-active-crons-before.txt | sort) <(pq payobook_template -c "select value from ir_config_parameter where key='pb_tenants.template_active_crons'" | tr ',' '\n' | sort) | paste -sd, -)"
echo "== rules on the three: rule sets / people on one / roster rows on one"
for db in $DBS; do echo "$db: $(pq $db -c "select count(*)||' (active '||count(*) filter (where state='active')||')' from pb_attendance_policy") / $(pq $db -c "select count(*) from hr_employee where pb_attendance_policy_id is not null") / $(pq $db -c "select count(*) from hr_shift_planning where pb_policy_id is not null")"; done
echo "== data: right before the stop vs installed (jobs, x_ and live_ lines excluded)"
for db in $DBS; do
  d=$(diff <(grep -vE '^(jobs_|x_|live_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-160; }
  echo "$db x_: $(diff <(grep -E '^x_' $EV/counts-before-$db.txt) <(grep -E '^x_' $EV/counts-installed-$db.txt) | grep -E '^[<>]' | cut -c1-140 | tr '\n' ' ')"
done
echo "== workforce data: prep -> now"
for db in $DBS; do
  bash /tmp/p7_counts.sh $db > $EV/counts-now-$db.txt 2>/dev/null
  for k in roster working_weeks shifts ot_rates ot_requests days_off leaves payslips mails_outgoing; do
    a=$(grep -h "^$k:" $EV/counts-prep-$db.txt); c=$(grep -h "^$k:" $EV/counts-now-$db.txt)
    [ "$a" = "$c" ] && echo "$db $k identical ($(echo $c | cut -c1-60))" || echo "$db $k DIFFERENT prep=[$a] now=[$c]"
  done
done
echo "== compiled code"
cp /tmp/p7_bundle.py $EV/ && chown odoo:odoo $EV/p7_bundle.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/p7_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db compiled code: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error\|Incompatible units' $EV/server-since-stop.log)"
echo "install logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
echo "rehearsal copies left: $(pq postgres -c "select count(*) from pg_database where datname like 'wfs_rh7%'")"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
