#!/bin/bash
# WFSETUP P10b: one phase of p10b_rh.py in an odoo-bin shell on the hidden copy. Root:
#   bash p10b_rh_run.sh <TS> <copy> <PHASE> <old|new> [OUT]
EV=/tmp/wfsetup-p10b-$1; COPY=$2; PH=$3; CODE=$4; OUT=${5:-$EV/$PH.json}
sudo -u odoo env PHASE=$PH OUT=$OUT python3 /odoo/odoo-server/odoo-bin shell -c $EV/$CODE.conf -d $COPY --no-http --max-cron-threads=0 < /tmp/p10b_rh.py > $EV/phase-$PH-$CODE.out 2>&1
echo "exit $?"; grep -E "PROBE|Traceback|Error" $EV/phase-$PH-$CODE.out | cut -c1-600
