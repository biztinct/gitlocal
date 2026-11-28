#!/bin/bash
# WFSETUP P8: run one phase of p8_rehearse.py in an odoo-bin shell on the hidden copy. Root: bash p8_run.sh <TS> <copy> <PHASE> [JOBS] [CONNECTORS]
EV=/tmp/wfsetup-p8-$1; COPY=$2
sudo -u odoo env PHASE=$3 JOBS="$4" CONNECTORS="$5" python3 /odoo/odoo-server/odoo-bin shell -c $EV/copy.conf -d $COPY --no-http --max-cron-threads=0 < /tmp/p8_rehearse.py > $EV/phase-$3.out 2>&1
echo "exit $?"; grep -E "PROBE|Traceback|Error" $EV/phase-$3.out | cut -c1-400
