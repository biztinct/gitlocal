#!/bin/bash
# DOCSTUDIO close-out D prep (no live change): staging from the pushed commit's archive, live trees =
# origin/19.1 trees (nobody shipped something newer), previous trees, PO gate, five dumps (rehearsal
# copy + roll-back) with file folders linked, counts, job snapshots, read-only probe as the
# administrator. Clone of w2/w2_prep.sh. Root: bash cd_prep.sh <TS>
TS=$1
EV=/tmp/cd-$TS
BK=/odoo/backups/docstudio-close-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/cd_mods.txt)
COMMIT=$(cat /tmp/cd_commit.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployCD && mkdir -p /tmp/deployCD/addons
tar -xf /tmp/cd_stage.tar -C /tmp/deployCD/addons
chown -R odoo:odoo /tmp/deployCD
bash /tmp/s2_hashtree.sh /tmp/deployCD/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/cd_commit_trees.txt >/dev/null && echo yes || echo NO)"
diff $EV/live-trees-before.txt /tmp/cd_base_trees.txt > $EV/live-vs-base.txt
log "live trees = origin/19.1 trees: $([ -s $EV/live-vs-base.txt ] && echo "NO: $(grep '^<' $EV/live-vs-base.txt | tr '\n' ';')" || echo yes)"
[ -s $EV/live-vs-base.txt ] && echo no > $EV/base.ok || echo yes > $EV/base.ok
log "pb_learn vi_VN.po staged = live: $(cmp -s /tmp/deployCD/addons/pb_learn/i18n/vi_VN.po $ADD/pb_learn/i18n/vi_VN.po && echo yes || echo NO) ($(wc -c < /tmp/deployCD/addons/pb_learn/i18n/vi_VN.po) bytes)"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS && log "previous trees saved ($(du -h $BK/previous-trees.tgz | cut -f1))"
log "python libraries for the server: $(sudo -u odoo python3 -c 'import lxml.etree, PyPDF2, openpyxl; print("lxml", ".".join(map(str, lxml.etree.LXML_VERSION)), "PyPDF2", PyPDF2.__version__, "openpyxl", openpyxl.__version__)' 2>&1 | tail -1)"
log "pdf engine: $(sudo -u odoo env PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin wkhtmltopdf --version 2>&1 | head -1)"
for f in pb_doc_studio_hiring/i18n/vi_VN.po pb_doc_studio_hiring/i18n/id_ID.po pb_hiring/i18n/id_ID.po pb_hiring/i18n/vi_VN.po pb_learn/i18n/vi_VN.po; do
  log "po gate $f: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('/tmp/deployCD/addons/$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done
DEPOK=yes
for db in $DBS; do
  miss=$(for m in $MODS; do st=$(sudo -u postgres psql -X -At -d $db -c "select state from ir_module_module where name='$m'"); [ "$st" = installed ] || echo -n "$m($st) "; done)
  log "$db: release modules not installed: ${miss:-none}"
  [ -n "$miss" ] && DEPOK=no
done
echo $DEPOK > $EV/deps.ok
cp /tmp/cd_probe.py $EV/ && chown odoo:odoo $EV/cd_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/cd_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
    < $EV/cd_probe.py > $EV/probe-before-$db.out 2>&1
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^PROBE|Traceback' $EV/probe-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1500)"
done
rm -f $EV/probe.conf
log "prep done (modules installed everywhere: $DEPOK, live = origin/19.1: $(cat $EV/base.ok))"
echo DONE > $EV/prep.result
