#!/bin/bash
# DOCSTUDIO W1A prep (no live change): staging from the pushed commit's archive, five dumps (rehearsal
# copy + roll-back), previous trees, counts, job snapshots, read-only probe as the administrator,
# server Python libraries. Clone of formstudio/fs16/fs16_prep.sh. Root: bash w1a_prep.sh <TS>
TS=$1
EV=/tmp/w1a-$TS
BK=/odoo/backups/docstudio-w1a-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/w1a_mods.txt)
COMMIT=$(cat /tmp/w1a_commit.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployW1A && mkdir -p /tmp/deployW1A/addons
tar -xf /tmp/w1a_stage.tar -C /tmp/deployW1A/addons
chown -R odoo:odoo /tmp/deployW1A
bash /tmp/s2_hashtree.sh /tmp/deployW1A/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/w1a_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live = 19.1 before: $(diff -q $EV/live-trees-before.txt /tmp/w1a_base_trees.txt >/dev/null && echo yes || echo NO)"
tar -C $ADD -czf $BK/previous-trees.tgz pb_explorer && log "previous trees saved (pb_explorer; the two new modules were absent) ($(du -h $BK/previous-trees.tgz | cut -f1))"
log "python libraries for the server: $(sudo -u odoo python3 -c 'import openpyxl, lxml.etree, polib; print("openpyxl", openpyxl.__version__, "lxml", ".".join(map(str, lxml.etree.LXML_VERSION)), "polib ok")' 2>&1 | tail -1)"
for m in pb_report_builder pb_excel_layout; do for l in vi_VN id_ID; do
  f=/tmp/deployW1A/addons/$m/i18n/$l.po
  [ -f $f ] && log "po gate $m/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
cp /tmp/w1a_probe.py $EV/ && chown odoo:odoo $EV/w1a_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/w1a_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
    < $EV/w1a_probe.py > $EV/probe-before-$db.out 2>&1
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^PROBE|Traceback' $EV/probe-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-600)"
done
rm -f $EV/probe.conf
log "prep done"
echo DONE > $EV/prep.result
