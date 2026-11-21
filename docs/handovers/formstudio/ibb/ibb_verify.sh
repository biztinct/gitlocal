#!/bin/bash
# INBOX-BULK-BANK verification (clone of fs13/fs13_verify.sh) after the go-live (read-only). Root: bash ibb_verify.sh <TS>
TS=$1
EV=/tmp/ibb-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/ibb_mods.txt)
{
echo "== trees"
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt $EV/staged-trees.txt && echo "all $(wc -l < $EV/staged-trees.txt) trees = commit"
echo "== versions (manifest vs latest_version)"
for db in $DBS; do
  while read -r m v h; do
    st=$(sudo -u postgres psql -X -At -d $db -c "select state||'|'||coalesce(latest_version,'') from ir_module_module where name='$m'")
    ok=MISMATCH; [ "${st#*|}" = "$v" ] && ok=ok
    echo "$db $m manifest $v db $st $ok"
  done < $EV/staged-trees.txt
done
echo "== jobs"
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  b=$(grep -c ',true$' $EV/cron-before-$db.txt); a=$(grep -c ',true$' $EV/cron-after-$db.txt)
  nb=$(wc -l < $EV/cron-before-$db.txt); na=$(wc -l < $EV/cron-after-$db.txt)
  echo "$db: total $nb -> $na, active $b -> $a; changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')"
done
echo "payobook job 156: $(sudo -u postgres psql -X -At -d payobook -c "select active from ir_cron where id=156")"
echo "== silent upgrade: nothing waiting changed; the one-time step"
for db in $DBS; do echo "$db: $(grep -E '^x_' $EV/counts-installed-$db.txt | tr '\n' ' ') (before: $(grep -E '^x_' $EV/counts-before-$db.txt | tr '\n' ' '))"; done
echo "== data: before the stop vs upgraded (jobs and the new column excluded)"
for db in $DBS; do
  d=$(diff <(grep -vE '^(jobs_|x_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-160; }
done
echo "== probes after (counts + pages)"
cp /tmp/ibb_probe.py $EV/ && chown odoo:odoo $EV/ibb_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  H=$([ $db = payobook ] && echo payobook.com || echo $db.payobook.com)
  for mode in counts pages; do
    sudo -u odoo env IBB_MODE=$mode PROBE_HOST=$H python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/ibb_probe.py > $EV/probe-$mode-after-$db.out 2>&1
    echo "$db $mode before: $(grep '^PROBE' $EV/probe-$mode-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1500)"
    echo "$db $mode after : $(grep -E '^PROBE|Traceback' $EV/probe-$mode-after-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1500)"
  done
  d=$(diff <(grep -E '^PROBE pages emp' $EV/probe-pages-before-$db.out) <(grep -E '^PROBE pages emp' $EV/probe-pages-after-$db.out))
  echo "$db /my + My Leave before vs after: $([ -z "$d" ] && echo byte-identical || echo DIFFERENT)"
done
rm -f $EV/probe.conf
echo "== upgrade steps"
grep -hE 'extra confirmation switched on' $EV/*-upgrade.log | sed 's/^\([0-9-]* [0-9:,]*\) [0-9]* INFO \([^ ]*\) [^ ]* /\2 /' | cut -c1-200
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
