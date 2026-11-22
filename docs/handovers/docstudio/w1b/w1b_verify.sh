#!/bin/bash
# DOCSTUDIO W1B verification after the go-live (read-only; the probe rolls back). Clone of
# w1a/w1a_verify.sh, plus the letter checks of the W1B handover (wording checksums, letters, vault
# documents, mail queue, sample PDF from the real engine, compiled code). Root: bash w1b_verify.sh <TS>
TS=$1
EV=/tmp/w1b-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/w1b_mods.txt)
{
echo "== trees"
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt $EV/staged-trees.txt && echo "all $(wc -l < $EV/staged-trees.txt) trees = commit"
echo "== versions (manifest vs latest_version)"
for db in $DBS; do
  while read -r m v h; do
    st=$(sudo -u postgres psql -X -At -d $db -c "select state||'|'||coalesce(latest_version,'') from ir_module_module where name='$m'")
    ok=MISMATCH; [ "${st#*|}" = "$v" ] && [ "${st%%|*}" = installed ] && ok=ok
    echo "$db $m manifest $v db $st $ok"
  done < $EV/staged-trees.txt
done
echo "== jobs (prep snapshot -> now)"
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  b=$(grep -c ',true$' $EV/cron-before-$db.txt); a=$(grep -c ',true$' $EV/cron-after-$db.txt)
  nb=$(wc -l < $EV/cron-before-$db.txt); na=$(wc -l < $EV/cron-after-$db.txt)
  echo "$db: total $nb -> $na, active $b -> $a; changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')"
done
echo "payobook job 156: $(sudo -u postgres psql -X -At -d payobook -c "select active from ir_cron where id=156")"
echo "== data: right before the stop vs installed (jobs and x_ lines excluded)"
for db in $DBS; do
  d=$(diff <(grep -vE '^(jobs_|x_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-160; }
  echo "$db x_: $(diff <(grep -E '^x_' $EV/counts-before-$db.txt) <(grep -E '^x_' $EV/counts-installed-$db.txt) | grep -E '^[<>]' | cut -c1-110 | tr '\n' ' ')"
done
echo "== letters: prep and right before the stop -> now (wording checksum, letters, vault documents)"
for db in $DBS; do for k in letter_templates letter_templates_written hr_letters employee_documents; do
  a=$(grep -h "^$k:" $EV/counts-prep-$db.txt); b=$(grep -h "^$k:" $EV/counts-before-$db.txt); c=$(bash /tmp/w1b_counts.sh $db 2>/dev/null | grep -h "^$k:")
  [ "$a" = "$c" ] && [ "$b" = "$c" ] && echo "$db $k identical ($c)" || echo "$db $k DIFFERENT prep=[$a] before=[$b] now=[$c]"
done; done
echo "== nothing mailed: mail queue before -> now"
for db in $DBS; do echo "$db: $(grep -h '^mail_queue' $EV/counts-before-$db.txt) -> $(bash /tmp/w1b_counts.sh $db | grep '^mail_queue')"; done
echo "== probe after (administrator, rolled back)"
cp /tmp/w1b_probe.py /tmp/w1b_bundle.py $EV/ && chown odoo:odoo $EV/w1b_probe.py $EV/w1b_bundle.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  sudo -u odoo PROBE_PDF=1 python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/w1b_probe.py > $EV/probe-after-$db.out 2>&1
  echo "$db after: $(grep -E '^PROBE|Traceback' $EV/probe-after-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/w1b_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db compiled code: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
echo "rehearsal copies left: $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'w1b%'")"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
