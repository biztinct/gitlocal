#!/bin/bash
# Root: add pb_lifecycle (WF2 P6e, files only) to this go-live. No live change.
# Staging = the final archive (5 modules); evidence lists follow; previous trees saved again
# (now with pb_lifecycle); live trees must equal the expected base (19.1 / bf2dba174).
TS=$1
EV=/tmp/fs12-$TS
BK=/odoo/backups/fs12-$TS
ADD=/odoo/odoo-server/addons
cp /tmp/fs12_mods3.txt /tmp/fs12_mods.txt
MODS=$(cat /tmp/fs12_mods.txt)
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -rf /tmp/deployFS12 && mkdir -p /tmp/deployFS12/addons
tar -xf /tmp/fs12_stage3.tar -C /tmp/deployFS12/addons
chown -R odoo:odoo /tmp/deployFS12
bash /tmp/s2_hashtree.sh /tmp/deployFS12/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "P6e added (pb_lifecycle files only); staged = commit: $(diff -q $EV/staged-trees.txt /tmp/fs12_commit_trees3.txt >/dev/null && echo yes || echo NO); live = expected base: $(diff -q $EV/live-trees-before.txt /tmp/fs12_base_trees3.txt >/dev/null && echo yes || echo NO)"
tar -C $ADD -czf $BK/previous-trees.tgz $(for m in $MODS; do [ -d $ADD/$m ] && echo $m; done) && log "previous trees saved again incl. pb_lifecycle ($(du -h $BK/previous-trees.tgz | cut -f1))"
f=/tmp/deployFS12/addons/pb_lifecycle/i18n/vi_VN.po
[ -f $f ] && log "po gate pb_lifecycle/vi_VN: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys; sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); print(len(rows),'entries ok')" 2>&1 | tail -1)"
