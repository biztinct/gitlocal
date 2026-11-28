#!/bin/bash
# NEWHIRE P7 verification after the go-live (read-only). Clone of ../p5b/nh_verify.sh: trees, versions
# (every shipped module incl. pb_new_hire installed at its manifest version on all five), jobs, data right
# before the stop vs after, the compiled code, server log, sites. Root: bash nh7_verify.sh <TS>
TS=$1
EV=/tmp/newhire-p7-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/nh7_mods.txt)
{
echo "== trees"
bash /tmp/nh7_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt $EV/staged-trees.txt && echo "all $(wc -l < $EV/staged-trees.txt) trees = commit $(cat /tmp/nh7_commit.txt)"
echo "== versions (manifest vs latest_version, 19.0. prefix normalised)"
for db in $DBS; do echo "$db: $(bash /tmp/nh7_vercheck.sh $db $EV/staged-trees.txt)"; done
echo "pb_new_hire installed on: $(for db in $DBS; do [ "$(sudo -u postgres psql -X -At -d $db -c "select state from ir_module_module where name='pb_new_hire'")" = installed ] && echo -n "$db "; done)"
echo "== jobs (prep snapshot -> now)"
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  b=$(grep -c ',true$' $EV/cron-before-$db.txt); a=$(grep -c ',true$' $EV/cron-after-$db.txt)
  nb=$(wc -l < $EV/cron-before-$db.txt); na=$(wc -l < $EV/cron-after-$db.txt)
  echo "$db: total $nb -> $na, active $b -> $a; changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')"
done
echo "payobook job 156: $(sudo -u postgres psql -X -At -d payobook -c "select active from ir_cron where id=156")"
echo "== data: right before the stop vs installed (jobs, x_ and live_ lines excluded)"
for db in $DBS; do
  [ -f $EV/counts-installed-$db.txt ] || { echo "$db: not upgraded"; continue; }
  d=$(diff <(grep -vE '^(jobs_|x_|live_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-200; }
  echo "$db x_: $(diff <(grep -E '^x_' $EV/counts-before-$db.txt) <(grep -E '^x_' $EV/counts-installed-$db.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
done
echo "== compiled code"
cp /tmp/nh7_bundle.py $EV/ && chown odoo:odoo $EV/nh7_bundle.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/nh7_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db compiled code: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
echo "== payroll-ready before (prep) -> after (B4)"
cp /tmp/nh7_ready.py /tmp/nh7_look.py $EV/ && chown odoo:odoo $EV/nh7_ready.py $EV/nh7_look.py
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/nh7_ready.py > $EV/ready-after-$db.out 2>&1
  b=$(grep '^PROBE' $EV/ready-before-$db.out | sed 's/| waiting.*//'); a=$(grep '^PROBE' $EV/ready-after-$db.out | sed 's/| waiting.*//')
  echo "$db: $([ -n "$a" ] && [ "$a" = "$b" ] && echo unchanged || echo CHANGED) - $(grep -E '^PROBE|Traceback' $EV/ready-after-$db.out | sed 's/^PROBE //' | cut -c1-260)"
done
echo "== look (read-only)"
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/nh7_look.py > $EV/look-$db.out 2>&1
  echo "$db: $(grep -E '^PROBE|Traceback' $EV/look-$db.out | sed 's/^PROBE //' | cut -c1-300 | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error\|Incompatible units' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
echo "rehearsal copies left: $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'nh7_rh%'")"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
