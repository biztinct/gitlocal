#!/bin/bash
# NEWHIRE P8 prep (no live change). Clone of ../p6/nh8_prep.sh:
#   staging from the pushed commit's archive; live trees must equal the BASE commit (19.1 before this
#   phase) - anything else on the server (newer or different) stops the release; previous trees; PO gate;
#   pb_new_hire's dependency closure + languages per database; five dumps + file-folder hard links; counts;
#   job snapshots; payroll-ready counts per database (nh8_ready.py, B4 before).
# Fresh dumps are taken again by nh8_golive.sh right before the stop.  Root: bash nh8_prep.sh <TS>
TS=$1
EV=/tmp/newhire-p8-$TS
BK=/odoo/backups/newhire-p8-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
STAGE=/tmp/deployNH8/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/nh8_mods.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV; chmod 700 $BK
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
fail() { log "$*"; echo FAILED > $EV/prep.result; exit 1; }
for f in /tmp/fs12_counts.sh /tmp/fsd_counts.sh /tmp/te_counts.sh /tmp/s2_counts.sh; do
  [ -f $f ] || fail "missing helper $f - stopping"; done
log "evidence $EV backups $BK commit $(cat /tmp/nh8_commit.txt)"
rm -rf /tmp/deployNH8 && mkdir -p $STAGE
tar -xf /tmp/nh8_stage.tar -C $STAGE
chown -R odoo:odoo /tmp/deployNH8
bash /tmp/nh8_hashtree.sh $STAGE $MODS > $EV/staged-trees.txt
bash /tmp/nh8_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
cp /tmp/nh8_base_trees.txt $EV/base-trees.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/nh8_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(tr '\n' ';' < $EV/live-trees-before.txt)"
log "base (19.1): $(tr '\n' ';' < $EV/base-trees.txt)"
log "staged:      $(tr '\n' ';' < $EV/staged-trees.txt)"
# every live tree must be 19.1's (the base commit): another session's newer or uncommitted copy stops us
if diff -q $EV/live-trees-before.txt $EV/base-trees.txt >/dev/null; then
  echo ok > $EV/version-check.txt
else
  { echo -n "LIVE-DIFFERS-FROM-19.1 "; diff $EV/base-trees.txt $EV/live-trees-before.txt | grep -E '^[<>]' | tr '\n' ' '; } > $EV/version-check.txt
fi
log "server trees vs 19.1: $(cat $EV/version-check.txt)"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS && log "previous trees saved ($MODS) ($(du -h $BK/previous-trees.tgz | cut -f1))"
for M in $MODS; do for l in vi_VN id_ID; do
  f=$STAGE/$M/i18n/$l.po
  [ -f $f ] || { log "po gate $M $l: no file"; continue; }
  log "po gate $M $l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, model',len([r for r in rows if r['type']=='model']),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
DEPS=$(python3 - $STAGE $ADD <<'PY'
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
  log "$db: dependencies not installed: ${miss:-none}; languages: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(code, ' ' order by code) from res_lang where active"); pb_new_hire: $(sudo -u postgres psql -X -At -d $db -c "select state||':'||coalesce(latest_version,'') from ir_module_module where name='pb_new_hire'")"
done
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || fail "DUMP FAILED $db"
  pg_restore -l $BK/$db.dump > /dev/null || fail "READBACK FAILED $db"
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/nh8_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db before: jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; $(grep -E '^(employees|contracts|journey_tasks|x_module_state):' $EV/counts-prep-$db.txt | cut -c1-140 | tr '\n' ';')"
done
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
cp /tmp/nh8_ready.py /tmp/nh8_look.py $EV/ && chown odoo:odoo $EV/nh8_ready.py $EV/nh8_look.py
for db in $DBS; do
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 < $EV/nh8_ready.py > $EV/ready-before-$db.out 2>&1
  log "$db payroll-ready before: $(grep -E '^PROBE|Traceback' $EV/ready-before-$db.out | sed 's/^PROBE //' | cut -c1-300)"
done
rm -f $EV/probe.conf
log "prep done"
echo DONE > $EV/prep.result
