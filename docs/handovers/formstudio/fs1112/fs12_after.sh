#!/bin/bash
# FS-11/FS-12 after the go-live. Root: bash fs12_after.sh <TS>
# 1. the read-only verification (trees, versions, jobs, data, probes as the administrator x5, log)
# 2. payobook.com only (the demo site): the showcase page (kept) and the pages opened for three demo
#    employees with it in place. Nothing is made on the four customer sites.
TS=$1
EV=/tmp/fs12-$TS
bash /tmp/fs12_verify.sh $TS
sed -e "s#^logfile.*#logfile = $EV/after-odoo.log#" /etc/odoo-server.conf > $EV/after.conf; chown odoo:odoo $EV/after.conf; chmod 600 $EV/after.conf
cp /tmp/fs12_publish.py $EV/fs12_publish.py; chown odoo:odoo $EV/fs12_publish.py
{
echo "== payobook.com showcase page"
sudo -u odoo env PUBLISH_DEMO=1 python3 /odoo/odoo-server/odoo-bin shell -c $EV/after.conf -d payobook --no-http --max-cron-threads=0 < $EV/fs12_publish.py > $EV/demo-publish.out 2>&1
grep -E '^PUB|Traceback' $EV/demo-publish.out
sudo -u odoo env PROBE_HOST=payobook.com python3 /odoo/odoo-server/odoo-bin shell -c $EV/after.conf -d payobook --no-http --max-cron-threads=0 < $EV/fs12_probe.py > $EV/demo-probe.out 2>&1
grep -E '^PROBE|Traceback' $EV/demo-probe.out | cut -c1-400
echo "payobook page layouts: $(sudo -u postgres psql -X -At -d payobook -c "select count(*)||' version '||max(version) from pb_form_layout where host_key='my_profile_page'")"
echo "other sites page layouts: $(for db in payobook_template p0clone rize sudima; do echo -n "$db $(sudo -u postgres psql -X -At -d $db -c "select count(*) from pb_form_layout where host_key='my_profile_page'") "; done)"
} 2>&1 | tee -a $EV/verify.txt
rm -f $EV/after.conf
touch $EV/after.done
