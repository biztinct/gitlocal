#!/bin/bash
# DOCSTUDIO PDFFIX verify after go-live (root): trees = staged, versions x5, engine, real PDFs per DB
# through the application (server shell, rolled back, nothing stored) with the service's own PATH.
EV=${EV:?}; M=$(cat /tmp/pdffix_mods.txt)
mkdir -p $EV && chown odoo:odoo $EV && chmod 750 $EV
python3 /tmp/pdffix2/treehash.py /odoo/odoo-server/addons $M > $EV/live.txt
python3 /tmp/pdffix2/treehash.py /tmp/deployPF $M > $EV/staged.txt
echo "trees live = staged: $(diff -q $EV/live.txt $EV/staged.txt >/dev/null && echo yes || echo NO)"
echo "engine on the service PATH: $(sudo -u odoo env PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin wkhtmltopdf --version | head -1); diversion: $(dpkg-divert --list /usr/bin/wkhtmltopdf)"
Q=$(echo $M | sed "s/\([a-z_]*\)/'\1'/g; s/ /,/g")
for db in payobook payobook_template p0clone rize sudima; do
  echo "$db: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||latest_version, ' ' order by name) from ir_module_module where state='installed' and name in ($Q)")"
done
cp /tmp/pdffix_probe.py $EV/ && chown odoo $EV/pdffix_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in payobook payobook_template p0clone rize sudima; do
  mkdir -p $EV/$db && chown odoo $EV/$db
  sudo -u odoo env PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin OUT=$EV/$db DB=$db python3 /odoo/odoo-server/odoo-bin shell \
    -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/pdffix_probe.py > $EV/$db.out 2>&1
  echo "$db: $(grep -E '^PROBE' $EV/$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-700)"
done
rm -f $EV/probe.conf
echo "server log ERROR since go-live: $(awk -v s="$(date -u -d '40 minutes ago' '+%Y-%m-%d %H:%M:%S')" '($1" "substr($2,1,8)) >= s' /var/log/odoo/odoo-server.log | grep -cE ' (ERROR|CRITICAL) ')"
echo VERIFY DONE
