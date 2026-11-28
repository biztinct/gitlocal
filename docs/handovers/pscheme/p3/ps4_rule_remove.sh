#!/bin/bash
# PSCHEME P4 follow-up runner (root): bash ps4_rule_remove.sh dry|apply <out folder>
# apply: deploy-notes START, a dump of rize first, the removal through the screen's method, the undo record,
# DONE (or FAILED). No restart.
MODE=$1; OUT=$2
case "$MODE" in dry|apply) ;; *) echo "dry or apply"; exit 1 ;; esac
TAG="Claude PSCHEME P4 rule"
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
mkdir -p $OUT && chmod 700 $OUT
if [ "$MODE" = apply ]; then
  note "START | rize data (owner decision): take off the Vietnam named-people rule beside the Vietnam country line, through Mapping > Other rules > Remove (fast lane); no restart | rize | dump $OUT/rize-before-rule-remove.dump; undo record $OUT/rize_vn_rule_remove_undo.txt. ABM untouched."
  sudo -u postgres pg_dump -Fc rize > $OUT/rize-before-rule-remove.dump && pg_restore -l $OUT/rize-before-rule-remove.dump > /dev/null \
    || { note "FAILED | not done: the dump could not be taken | rize | nothing changed"; exit 1; }
fi
W=$(mktemp -d /tmp/ps4r.XXXXXX); chown odoo:odoo $W; chmod 700 $W
sed -e "s#^logfile.*#logfile = $W/odoo.log#" /etc/odoo-server.conf > $W/c.conf; chown odoo:odoo $W/c.conf; chmod 600 $W/c.conf
cp /tmp/ps4_rule_remove.py /tmp/ps3_settle.py $W/ && chown odoo:odoo $W/*.py
sudo -u odoo env PS3_MODE=$MODE PS3_OUT=$W python3 /odoo/odoo-server/odoo-bin shell -c $W/c.conf -d rize --no-http --max-cron-threads=0 < $W/ps4_rule_remove.py > $W/remove-$MODE.out 2>&1
if [ "$MODE" = apply ] && grep -q '^PROBE committed' $W/remove-$MODE.out; then
  sudo -u odoo env PS3_CID=1 python3 /odoo/odoo-server/odoo-bin shell -c $W/c.conf -d rize --no-http --max-cron-threads=0 < $W/ps3_settle.py > $W/settle.out 2>&1
fi
rm -f $W/c.conf; cp -a $W/. $OUT/ && rm -rf $W
grep -hE '^PROBE|Traceback|Error' $OUT/remove-$MODE.out $OUT/settle.out 2>/dev/null | cut -c1-900
if [ "$MODE" = apply ]; then
  if grep -q '^PROBE committed' $OUT/remove-$MODE.out; then note "DONE | rize Vietnam named-people rule taken off | rize | $(grep '^PROBE removed' $OUT/remove-$MODE.out | cut -c1-160); answers identical with and without own pay schemes; $(grep '^PROBE settled' $OUT/settle.out | sed 's/^PROBE //'); undo $OUT/rize_vn_rule_remove_undo.txt. ABM untouched."
  else note "FAILED | rize Vietnam named-people rule | rize | nothing committed (checks or error; see $OUT/remove-$MODE.out). ABM untouched."; fi
fi
