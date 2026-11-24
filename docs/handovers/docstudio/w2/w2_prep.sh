#!/bin/bash
# DOCSTUDIO W2 prep (no live change): staging from the pushed commit's archive, previous trees, five
# dumps (rehearsal copy + roll-back), dependency check per database, counts, job snapshots, read-only
# probe as the administrator, server Python libraries, PO gate, PDF engine and fonts.
# Clone of w1b/w1b_prep.sh (+ w1a's previous trees). Root: bash w2_prep.sh <TS>
TS=$1
EV=/tmp/w2-$TS
BK=/odoo/backups/docstudio-w2-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/w2_mods.txt)
NEW="pb_doc_studio_hiring pb_doc_studio_me pb_doc_contracts pb_report_pdf pb_report_pdf_send"
COMMIT=$(cat /tmp/w2_commit.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployW2 && mkdir -p /tmp/deployW2/addons
tar -xf /tmp/w2_stage.tar -C /tmp/deployW2/addons
chown -R odoo:odoo /tmp/deployW2
bash /tmp/s2_hashtree.sh /tmp/deployW2/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/w2_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-trees-before.txt | tr '\n' ';')"
tar -C $ADD -czf $BK/previous-trees.tgz pb_doc_studio pb_report_builder pb_explorer && log "previous trees saved (pb_doc_studio pb_report_builder pb_explorer; the five new modules are absent) ($(du -h $BK/previous-trees.tgz | cut -f1))"
log "python libraries for the server: $(sudo -u odoo python3 -c 'import lxml.etree, markupsafe, polib, openpyxl, PyPDF2; print("lxml", ".".join(map(str, lxml.etree.LXML_VERSION)), "openpyxl", openpyxl.__version__, "PyPDF2", PyPDF2.__version__, "polib ok")' 2>&1 | tail -1)"
log "pdf engine: $(wkhtmltopdf --version 2>&1 | head -1); fonts: DejaVu Sans $(fc-list | grep -c 'DejaVuSans') DejaVu Serif $(fc-list | grep -ci 'DejaVu Serif') system files; Roboto system $(fc-list | grep -ci roboto); web fonts $(for f in Roboto Open_Sans Montserrat; do echo -n "$f $(ls $ADD/web/static/fonts/google/$f/ 2>/dev/null | grep -cE 'Regular|Bold|Italic') "; done)"
for m in $NEW; do for l in vi_VN id_ID; do
  f=/tmp/deployW2/addons/$m/i18n/$l.po
  [ -f $f ] && log "po gate $m/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
# every dependency of every new module installed on every database (else STOP before go-live)
DEPS=$(cd /tmp/deployW2/addons && python3 -c "
import ast
new = '$NEW'.split()
d = set()
for m in new:
    d |= set(ast.literal_eval(open(m + '/__manifest__.py').read()).get('depends', []))
print(' '.join(sorted(d - set(new))))")
log "dependencies of the new modules: $DEPS"
DEPOK=yes
for db in $DBS; do
  miss=$(for d in $DEPS; do st=$(sudo -u postgres psql -X -At -d $db -c "select state from ir_module_module where name='$d'"); [ "$st" = installed ] || echo -n "$d($st) "; done)
  already=$(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||state, ' ') from ir_module_module where name in ('pb_doc_studio_hiring','pb_doc_studio_me','pb_doc_contracts','pb_report_pdf','pb_report_pdf_send')")
  log "$db: missing dependencies: ${miss:-none}; new modules known: ${already:-none}"
  [ -n "$miss" ] && DEPOK=no
done
echo $DEPOK > $EV/deps.ok
cp /tmp/w2_probe.py $EV/ && chown odoo:odoo $EV/w2_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/w2_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
    < $EV/w2_probe.py > $EV/probe-before-$db.out 2>&1
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^PROBE|Traceback' $EV/probe-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-700)"
done
rm -f $EV/probe.conf
log "prep done (dependencies ok: $DEPOK)"
echo DONE > $EV/prep.result
