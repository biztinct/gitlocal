#!/bin/bash
# PSCHEME P3 verification after the go-live (read-only). Clone of ../../newhire/p8/nh8_verify.sh: trees,
# versions (every shipped module installed at its manifest version on all five), jobs (prep snapshot ->
# now: identical except the ONE new daily job; none re-activated; payobook job 156 still off), data right
# before the stop vs after, the compiled code + the engine with 0 rows (ps3_bundle.py), "who pays each
# person" right before the stop (old code) vs now (new code) - must be identical, server log, sites.
# Root: bash ps3_verify.sh <TS>
TS=$1
EV=/tmp/pscheme-p3-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/ps3_mods.txt)
{
echo "== trees"
bash /tmp/ps3_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt $EV/staged-trees.txt && echo "all $(wc -l < $EV/staged-trees.txt) trees = commit $(cat /tmp/ps3_commit.txt)"
echo "== versions (manifest vs latest_version, 19.0. prefix normalised)"
for db in $DBS; do echo "$db: $(bash /tmp/ps3_vercheck.sh $db $EV/staged-trees.txt)"; done
echo "== jobs (prep snapshot -> now)"
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  b=$(grep -c ',true$' $EV/cron-before-$db.txt); a=$(grep -c ',true$' $EV/cron-after-$db.txt)
  nb=$(wc -l < $EV/cron-before-$db.txt); na=$(wc -l < $EV/cron-after-$db.txt)
  new=$(join -t, -v2 <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | cut -d, -f1 | paste -sd' ' -)
  newx=$(for i in $new; do sudo -u postgres psql -X -At -d $db -c "select d.module||'.'||d.name||'('||c.active||')' from ir_model_data d join ir_cron c on c.id=d.res_id where d.model='ir.cron' and d.res_id=$i"; done | paste -sd' ' -)
  reon=$(join -t, <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -)
  off=$(join -t, <(sort $EV/cron-before-$db.txt) <(sort $EV/cron-after-$db.txt) | awk -F, '$2=="true" && $3=="false" {print $1}' | paste -sd, -)
  echo "$db: total $nb -> $na, active $b -> $a; new: ${newx:-none}; re-activated: ${reon:-none}; switched off: ${off:-none}"
done
echo "payobook job 156: $(sudo -u postgres psql -X -At -d payobook -c "select active from ir_cron where id=156")"
echo "== data: right before the stop vs installed (jobs, x_ and live_ lines excluded)"
for db in $DBS; do
  [ -f $EV/counts-installed-$db.txt ] || { echo "$db: not upgraded"; continue; }
  d=$(diff <(grep -vE '^(jobs_|x_|live_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-200; }
  echo "$db x_: $(diff <(grep -E '^x_' $EV/counts-before-$db.txt) <(grep -E '^x_' $EV/counts-installed-$db.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
done
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
cp /tmp/ps3_bundle.py /tmp/ps3_who.py $EV/ && chown odoo:odoo $EV/ps3_bundle.py $EV/ps3_who.py
echo "== compiled code + the engine with no rows"
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/ps3_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
echo "== who pays each active person: right before the stop (old code) -> now (new code)"
for db in $DBS; do
  sudo -u odoo env PS3_OUT=$EV/who-after-$db.json python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/ps3_who.py > $EV/who-after-$db.out 2>&1
  echo "$db: $( [ -s $EV/who-golive-$db.json ] && cmp -s $EV/who-golive-$db.json $EV/who-after-$db.json && echo identical || echo DIFFERENT) - $(grep -E '^PROBE|Traceback' $EV/who-after-$db.out | sed 's/^PROBE //' | cut -c1-200)"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error\|Incompatible units' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
grep -hE ' (ERROR|CRITICAL) ' $EV/*-upgrade.log 2>/dev/null | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | cut -c1-200 | sort | uniq -c | head -8
echo "rehearsal copies left: $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'ps3_rh%'")"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
