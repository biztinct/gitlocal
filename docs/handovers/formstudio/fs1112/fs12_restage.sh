#!/bin/bash
# Root: refresh the staging folder with the final commit's archive; the evidence's staged trees follow.
TS=$1
EV=/tmp/fs12-$TS
MODS=$(cat /tmp/fs12_mods.txt)
rm -rf /tmp/deployFS12 && mkdir -p /tmp/deployFS12/addons
tar -xf /tmp/fs12_stage2.tar -C /tmp/deployFS12/addons
chown -R odoo:odoo /tmp/deployFS12
bash /tmp/s2_hashtree.sh /tmp/deployFS12/addons $MODS > $EV/staged-trees.txt
echo "$(date -u +%T) restaged from the final commit; staged = commit: $(diff -q $EV/staged-trees.txt /tmp/fs12_commit_trees2.txt >/dev/null && echo yes || echo NO)" | tee -a $EV/steps.log
cp /tmp/fs12_probe_v2.py /tmp/fs12_probe.py
