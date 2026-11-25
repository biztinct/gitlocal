#!/bin/bash
# DOCSTUDIO PDFFIX-2 verify (root): trees = staged, versions x5, then every shipped wording (letters,
# offers, certificates, contracts; en + vi) and a real contract document per database through the
# application with the live engine (server shell, rolled back, nothing stored): page counts.
EV=${EV:?}; M=$(cat /tmp/pdffix_mods.txt)
mkdir -p $EV && chown odoo:odoo $EV && chmod 750 $EV
python3 /tmp/treehash.py /odoo/odoo-server/addons $M > $EV/live.txt; python3 /tmp/treehash.py /tmp/deployPF $M > $EV/staged.txt
echo "trees live = staged: $(diff -q $EV/live.txt $EV/staged.txt >/dev/null && echo yes || echo NO)"
for db in payobook payobook_template p0clone rize sudima; do
  echo "$db: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||latest_version, ' ' order by name) from ir_module_module where state='installed' and name in ('pb_doc_studio','pb_doc_contracts')")"
done
cp /tmp/pdffix_pages_probe.py $EV/ && chown odoo $EV/pdffix_pages_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/p.conf; chown odoo $EV/p.conf; chmod 600 $EV/p.conf
for db in payobook payobook_template p0clone rize sudima; do
  mkdir -p $EV/$db && chown odoo $EV/$db
  sudo -u odoo env PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin OUT=$EV/$db MODE=live python3 /odoo/odoo-server/odoo-bin shell \
    -c $EV/p.conf -d $db --no-http --max-cron-threads=0 < $EV/pdffix_pages_probe.py 2>&1 | grep '^PROBE' > $EV/$db.txt
  echo "$db: $(sed 's/^PROBE //; s/lastpage_chars/last/; s/ |.*//' $EV/$db.txt | grep -v 'rolled back' | awk '{print $1"/"$2":"$(NF-2)"p,"$NF}' | tr '\n' ' ')"
done
rm -f $EV/p.conf; echo VERIFY DONE
