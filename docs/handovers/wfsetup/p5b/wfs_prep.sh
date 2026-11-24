#!/bin/bash
# WFSETUP P5b prep (no live change): staging from the pushed commit's archive, live trees vs commit,
# previous trees, five dumps + file-folder hard links (rehearsal copy + roll-back), dependency check per
# database, counts, job snapshots, languages. Clone of docstudio/w2/w2_prep.sh. Root: bash wfs_prep.sh <TS>
TS=$1
EV=/tmp/wfsetup-$TS
BK=/odoo/backups/wfsetup-p5b-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/wfs_mods.txt)
COMMIT=$(cat /tmp/wfs_commit.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployWFS && mkdir -p /tmp/deployWFS/addons
tar -xf /tmp/wfs_stage.tar -C /tmp/deployWFS/addons
chown -R odoo:odoo /tmp/deployWFS
bash /tmp/s2_hashtree.sh /tmp/deployWFS/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/wfs_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-trees-before.txt | tr '\n' ';')"
log "staged:      $(cat $EV/staged-trees.txt | tr '\n' ';')"
# pb_attendance_policy ships unchanged: its live tree must already be the commit's
log "pb_attendance_policy live = commit: $(diff -q <(grep '^pb_attendance_policy ' $EV/live-trees-before.txt) <(grep '^pb_attendance_policy ' $EV/staged-trees.txt) >/dev/null && echo yes || echo NO)"
tar -C $ADD -czf $BK/previous-trees.tgz pb_workforce_workspace pb_hr_workforce pb_attendance_policy && log "previous trees saved (pb_workforce_workspace pb_hr_workforce pb_attendance_policy; pb_workforce_setup is absent) ($(du -h $BK/previous-trees.tgz | cut -f1))"
for m in pb_workforce_setup pb_workforce_workspace; do for l in vi_VN id_ID; do
  f=/tmp/deployWFS/addons/$m/i18n/$l.po
  [ -f $f ] && log "po gate $m/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
# dependency closure of pb_workforce_setup (the server's manifests for everything not staged)
DEPS=$(python3 - /tmp/deployWFS/addons $ADD <<'PY'
import ast, os, sys
stage, add = sys.argv[1], sys.argv[2]
def deps(m):
    for root in (stage, add):
        p = os.path.join(root, m, '__manifest__.py')
        if os.path.exists(p):
            return ast.literal_eval(open(p).read()).get('depends', [])
    return []
seen, todo = set(), ['pb_workforce_setup']
while todo:
    m = todo.pop()
    for d in deps(m):
        if d not in seen:
            seen.add(d); todo.append(d)
print(' '.join(sorted(seen)))
PY
)
log "dependency closure of pb_workforce_setup: $(echo $DEPS | wc -w) modules"
for db in $DBS; do
  miss=$(for d in $DEPS; do st=$(sudo -u postgres psql -X -At -d $db -c "select state from ir_module_module where name='$d'"); [ "$st" = installed ] || echo -n "$d($st) "; done)
  log "$db: dependencies not installed: ${miss:-none}; languages: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(code, ' ' order by code) from res_lang where active")"
done
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/wfs_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^(roster|working_weeks|x_rule_sets|ot_requests|employees):' $EV/counts-prep-$db.txt | cut -c1-90 | tr '\n' ';')"
done
log "prep done"
echo DONE > $EV/prep.result
