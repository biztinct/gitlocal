#!/bin/bash
# PSCHEME F1 runner (root): bash ps3f1_run.sh dry|apply <out folder>
# apply: deploy-notes START, a dump of rize first, the rule, the undo record, DONE (or FAILED).
MODE=$1; OUT=$2
case "$MODE" in dry|apply) ;; *) echo "dry or apply"; exit 1 ;; esac
TAG="Claude PSCHEME F1"
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
mkdir -p $OUT && chmod 700 $OUT
if [ "$MODE" = apply ]; then
  note "START | rize data (owner-ordered): the Vietnam scheme gets a by-country rule like India / Singapore / Indonesia (Country of work = Vietnam); no restart | rize | dump $OUT/rize-before-rule.dump; undo record $OUT/rize_vn_rule_undo.txt. ABM untouched."
  sudo -u postgres pg_dump -Fc rize > $OUT/rize-before-rule.dump && pg_restore -l $OUT/rize-before-rule.dump > /dev/null \
    || { note "FAILED | rule not written: the dump could not be taken | rize | nothing changed"; exit 1; }
fi
W=$(mktemp -d /tmp/ps3f1.XXXXXX); chown odoo:odoo $W; chmod 700 $W
sed -e "s#^logfile.*#logfile = $W/odoo.log#" /etc/odoo-server.conf > $W/c.conf; chown odoo:odoo $W/c.conf; chmod 600 $W/c.conf
cp /tmp/ps3f1_rule.py $W/ && chown odoo:odoo $W/ps3f1_rule.py
sudo -u odoo env PS3_MODE=$MODE PS3_OUT=$W python3 /odoo/odoo-server/odoo-bin shell -c $W/c.conf -d rize --no-http --max-cron-threads=0 < $W/ps3f1_rule.py > $W/rule-$MODE.out 2>&1
rm -f $W/c.conf; cp -a $W/. $OUT/ && rm -rf $W
grep -E '^PROBE|Traceback|Error' $OUT/rule-$MODE.out | cut -c1-1500
if [ "$MODE" = apply ]; then
  if grep -q '^PROBE committed' $OUT/rule-$MODE.out; then note "DONE | rize Vietnam by-country rule | rize | $(grep '^PROBE committed' $OUT/rule-$MODE.out | sed 's/^PROBE //'); checks passed; undo $OUT/rize_vn_rule_undo.txt. ABM untouched."
  else note "FAILED | rize Vietnam by-country rule | rize | nothing committed (checks or error; see $OUT/rule-$MODE.out). ABM untouched."; fi
fi
