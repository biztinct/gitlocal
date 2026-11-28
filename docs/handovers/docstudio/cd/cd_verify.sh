#!/bin/bash
# DOCSTUDIO close-out D verification after the go-live (read-only; the probe rolls back). Clone of
# w2/w2_verify.sh: trees, versions, jobs, data (prep -> right before the stop -> now), the letter
# wording, letters, vault documents, offers, certificates, mail queue, the analytics Print menu, the
# probe with real PDFs (Z1 offer pay words, Z3 names, Z4 contract preview language, L lessons), the
# compiled screen code, server log. Root: bash cd_verify.sh <TS>
TS=$1
EV=/tmp/cd-$TS
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/cd_mods.txt)
{
echo "== trees"
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-verify.txt
diff $EV/live-trees-verify.txt $EV/staged-trees.txt && echo "all $(wc -l < $EV/staged-trees.txt) trees = commit $(cat /tmp/cd_commit.txt)"
echo "pb_learn vi_VN.po: $(md5sum < $ADD/pb_learn/i18n/vi_VN.po | cut -c1-12) live, $(md5sum < /tmp/deployCD/addons/pb_learn/i18n/vi_VN.po | cut -c1-12) commit, $(wc -c < $ADD/pb_learn/i18n/vi_VN.po) bytes, $(grep -c '^msgid ' $ADD/pb_learn/i18n/vi_VN.po) msgid"
echo "== versions (manifest vs latest_version)"
for db in $DBS; do
  bad=""
  while read -r m v h; do
    st=$(sudo -u postgres psql -X -At -d $db -c "select state||'|'||coalesce(latest_version,'') from ir_module_module where name='$m'")
    [ "${st#*|}" = "$v" ] && [ "${st%%|*}" = installed ] || bad="$bad $m($st vs $v)"
  done < $EV/staged-trees.txt
  echo "$db: $([ -z "$bad" ] && echo "12/12 installed at the manifest version" || echo "MISMATCH$bad")"
done
echo "== jobs (prep snapshot -> now)"
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-after-$db.txt
  b=$(grep -c ',true$' $EV/cron-before-$db.txt); a=$(grep -c ',true$' $EV/cron-after-$db.txt)
  nb=$(wc -l < $EV/cron-before-$db.txt); na=$(wc -l < $EV/cron-after-$db.txt)
  echo "$db: total $nb -> $na, active $b -> $a; changed: $(diff $EV/cron-before-$db.txt $EV/cron-after-$db.txt | grep -E '^[<>]' | tr '\n' ' ')"
done
echo "== data: right before the stop vs installed (jobs and x_ lines excluded)"
for db in $DBS; do
  d=$(diff <(grep -vE '^(jobs_|x_)' $EV/counts-before-$db.txt) <(grep -vE '^(jobs_|x_)' $EV/counts-installed-$db.txt))
  [ -z "$d" ] && echo "$db: identical" || { echo "$db: DIFFERENT"; echo "$d" | cut -c1-160; }
  echo "$db x_: $(diff <(grep -E '^x_' $EV/counts-before-$db.txt) <(grep -E '^x_' $EV/counts-installed-$db.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
done
echo "== prep and right before the stop -> now"
for db in $DBS; do
  bash /tmp/cd_counts.sh $db > $EV/counts-now-$db.txt
  for k in letter_templates_wording letter_templates_written letter_template_names_en doc_versions hr_letters employee_documents hiring_offers certificates mail_queue saved_reports learn_progress x_analytics_print_menu; do
    a=$(grep -h "^$k:" $EV/counts-prep-$db.txt); b=$(grep -h "^$k:" $EV/counts-before-$db.txt); c=$(grep -h "^$k:" $EV/counts-now-$db.txt)
    [ "$a" = "$c" ] && [ "$b" = "$c" ] && echo "$db $k identical ($c)" || echo "$db $k CHANGED prep=[$a] before=[$b] now=[$c]"
  done
done
echo "== probe after (administrator, real PDFs, rolled back)"
cp /tmp/cd_probe.py $EV/ && chown odoo:odoo $EV/cd_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  sudo -u odoo PROBE_PDF=1 python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/cd_probe.py > $EV/probe-after-$db.out 2>&1
  echo "$db after: $(grep -E '^PROBE|Traceback' $EV/probe-after-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== compiled screen code (odoo-bin shell, rolled back)"
cp /tmp/cd_bundle.py $EV/ && chown odoo:odoo $EV/cd_bundle.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/cd_bundle.py > $EV/bundle-$db.out 2>&1
  echo "$db: $(grep -E '^PROBE|Traceback' $EV/bundle-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
echo "== server log since the stop"
N=$(cat $EV/log-line-at-stop.txt)
tail -n +$((N+1)) /var/log/odoo/odoo-server.log > $EV/server-since-stop.log
echo "lines $(wc -l < $EV/server-since-stop.log); ERROR/CRITICAL: $(grep -cE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log), Traceback: $(grep -c Traceback $EV/server-since-stop.log)"
grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' $EV/server-since-stop.log | cut -c1-240 | head -10
echo "assets errors: $(grep -c 'assetsbundle: Error\|css error' $EV/server-since-stop.log)"
echo "upgrade logs: $(cat $EV/*-upgrade.log 2>/dev/null | grep -cE ' (ERROR|CRITICAL) ') ERROR, $(cat $EV/*-upgrade.log 2>/dev/null | grep -c Traceback) Traceback"
cat $EV/*-upgrade.log 2>/dev/null | grep -E ' (ERROR|CRITICAL) ' | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | cut -c1-200 | sort | uniq -c | head -10
echo "rehearsal copies left: $(sudo -u postgres psql -X -At -d postgres -c "select count(*) from pg_database where datname like 'cd_rh%'")"
echo "service processes: $(ps -eo cmd | grep -c '[o]doo-bin -c /etc/odoo-server.conf$')"
for h in payobook.com payobook_template.payobook.com p0clone.payobook.com rize.payobook.com sudima.payobook.com; do
  echo "$h login: $(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8069/web/login)"
done
} 2>&1 | tee $EV/verify.txt
