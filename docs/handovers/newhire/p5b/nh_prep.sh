#!/bin/bash
# NEWHIRE P5b prep (no live change): staging from the pushed commit's archive, live trees vs commit,
# previous trees, PO gate, pb_new_hire's dependency closure per database, languages, document readers,
# five dumps + file-folder hard links (rehearsal copies + roll-back), counts, job snapshots.
# Clone of ../../wfsetup/p5b/wfs_prep.sh. Fresh dumps are taken again by nh_golive.sh right before the stop.
# Root: bash nh_prep.sh <TS>
TS=$1
EV=/tmp/newhire-p5b-$TS
BK=/odoo/backups/newhire-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/nh_mods.txt)
SHARED="pb_learn pb_people pb_hr_payroll_formula pb_probation pb_scheme_map"
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV; chmod 700 $BK
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
for f in /tmp/fs12_counts.sh /tmp/fsd_counts.sh /tmp/te_counts.sh /tmp/s2_counts.sh; do
  [ -f $f ] || { log "missing helper $f - stopping"; echo FAILED > $EV/prep.result; exit 1; }; done
log "evidence $EV backups $BK commit $(cat /tmp/nh_commit.txt)"
rm -rf /tmp/deployNH && mkdir -p /tmp/deployNH/addons
tar -xf /tmp/nh_stage.tar -C /tmp/deployNH/addons
chown -R odoo:odoo /tmp/deployNH
bash /tmp/nh_hashtree.sh /tmp/deployNH/addons $MODS > $EV/staged-trees.txt
bash /tmp/nh_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/nh_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-trees-before.txt | tr '\n' ';')"
log "staged:      $(cat $EV/staged-trees.txt | tr '\n' ';')"
# the live copies must be origin/19.1's (checked before staging with the base archive); a newer
# version on the server stops the release
python3 - "$EV/live-trees-before.txt" "$EV/staged-trees.txt" > $EV/version-check.txt <<'PY'
import sys
def rd(p):
    d = {}
    for line in open(p):
        parts = line.split()
        if len(parts) >= 2 and parts[1] != 'ABSENT':
            d[parts[0]] = tuple(int(x) for x in parts[1].split('.'))
    return d
live, new = rd(sys.argv[1]), rd(sys.argv[2])
bad = [m for m in new if m in live and live[m] > new[m]]
print('NEWER-ON-SERVER ' + ' '.join(bad) if bad else 'ok')
PY
log "server versions vs shipped: $(cat $EV/version-check.txt)"
tar -C $ADD -czf $BK/previous-trees.tgz $SHARED && log "previous trees saved ($SHARED; pb_new_hire is absent) ($(du -h $BK/previous-trees.tgz | cut -f1))"
for M in pb_new_hire pb_people pb_learn; do for l in vi_VN id_ID; do
  f=/tmp/deployNH/addons/$M/i18n/$l.po
  [ -f $f ] || { log "po gate $M $l: no file"; continue; }
  log "po gate $M $l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
DEPS=$(python3 - /tmp/deployNH/addons $ADD <<'PY'
import ast, os, sys
stage, add = sys.argv[1], sys.argv[2]
def deps(m):
    for root in (stage, add):
        p = os.path.join(root, m, '__manifest__.py')
        if os.path.exists(p):
            return ast.literal_eval(open(p).read()).get('depends', [])
    return []
seen, todo = set(), ['pb_new_hire']
while todo:
    m = todo.pop()
    for d in deps(m):
        if d not in seen:
            seen.add(d); todo.append(d)
print(' '.join(sorted(seen)))
PY
)
log "dependency closure of pb_new_hire: $(echo $DEPS | wc -w) modules"
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
  bash /tmp/nh_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^(employees|contracts|newhire_proposals|lifecycle_reminder_job|doc_readers|x_module_state):' $EV/counts-prep-$db.txt | cut -c1-120 | tr '\n' ';')"
done
log "prep done"
echo DONE > $EV/prep.result
