#!/bin/bash
# WFSETUP P6 verification after the go-live (read-only). Root: bash p6_verify.sh <TS>
TS=$1
EV=/tmp/wfsetup-p6-$TS
ADD=/odoo/odoo-server/addons
M=pb_workforce_setup
ALLDBS="payobook payobook_template p0clone rize sudima"
WANTV=$(python3 -c "import ast;print(ast.literal_eval(open('/tmp/deployWFS6/addons/$M/__manifest__.py').read())['version'])")
{
echo "== tree"
bash /tmp/s2_hashtree.sh $ADD $M > $EV/live-tree-verify.txt
diff $EV/live-tree-verify.txt $EV/staged-tree.txt && echo "tree = commit: $(cat $EV/staged-tree.txt)"
echo "== versions (manifest $WANTV)"
for db in $ALLDBS; do
  echo "$db $M $(sudo -u postgres psql -X -At -d $db -c "select coalesce((select state||':'||coalesce(latest_version,'') from ir_module_module where name='$M'),'absent')")"
done
echo "== jobs (prep snapshot -> now)"
for db in $ALLDBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  echo "$db: total $(wc -l < $EV/cron-before-$db.txt) -> $(wc -l < $EV/cron-after-$db.txt), active $(grep -c ',true$' $EV/cron-before-$db.txt) -> $(grep -c ',true$' $EV/cron-after-$db.txt); changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')"
done
echo "== data: right before the stop vs installed (live_ lines excluded)"
for db in sudima payobook; do
  d=$(diff <(grep -vE '^(jobs_|live_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|live_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-160; }
done
echo "== clocks: send switch per connector (must be unchanged; nothing switched on)"
for db in sudima payobook; do
  echo "$db: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(id||':'||publish_punches::text, ' ' order by id) from pb_clock_connector")"
done
echo "== compiled code"
cp /tmp/p6_bundle.py $EV/ && chown odoo:odoo $EV/p6_bundle.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in sudima payobook; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/p6_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db compiled code: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error\|Incompatible units' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
