#!/bin/bash
# DOCSTUDIO W1B prep (no live change): staging from the pushed commit's archive, five dumps (rehearsal
# copy + roll-back), counts, job snapshots, read-only probe as the administrator, server Python
# libraries, PO gate, PDF engine and fonts. Clone of w1a/w1a_prep.sh. Root: bash w1b_prep.sh <TS>
TS=$1
EV=/tmp/w1b-$TS
BK=/odoo/backups/docstudio-w1b-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/w1b_mods.txt)
COMMIT=$(cat /tmp/w1b_commit.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployW1B && mkdir -p /tmp/deployW1B/addons
tar -xf /tmp/w1b_stage.tar -C /tmp/deployW1B/addons
chown -R odoo:odoo /tmp/deployW1B
bash /tmp/s2_hashtree.sh /tmp/deployW1B/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/w1b_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-trees-before.txt) (expected ABSENT: a new module)"
log "python libraries for the server: $(sudo -u odoo python3 -c 'import lxml.etree, markupsafe, polib; print("lxml", ".".join(map(str, lxml.etree.LXML_VERSION)), "markupsafe ok polib ok")' 2>&1 | tail -1)"
log "pdf engine: $(wkhtmltopdf --version 2>&1 | head -1); fonts: DejaVu Serif $(fc-list | grep -ci 'DejaVu Serif') system files; web fonts $(for f in Roboto Open_Sans Montserrat; do echo -n "$f $(ls $ADD/web/static/fonts/google/$f/ 2>/dev/null | grep -cE 'Regular|Bold|Italic') "; done)"
for l in vi_VN id_ID; do
  f=/tmp/deployW1B/addons/pb_doc_studio/i18n/$l.po
  [ -f $f ] && log "po gate pb_doc_studio/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done
cp /tmp/w1b_probe.py $EV/ && chown odoo:odoo $EV/w1b_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/w1b_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
    < $EV/w1b_probe.py > $EV/probe-before-$db.out 2>&1
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^PROBE|Traceback' $EV/probe-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-600)"
done
rm -f $EV/probe.conf
log "prep done"
echo DONE > $EV/prep.result
