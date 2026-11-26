#!/bin/bash
# PSCHEME P3 D.2: the one-time fill ("Give everyone their own pay scheme") on ONE live database, through
# the Mapping board's own calls (ps3_fill.py). NOT run by the release: it waits for the owner.
#   dry    read-only, rolled back: the counts per company (writes nothing anywhere)
#   apply  START line in /opt/deploy-notes.md, a fresh dump of that database (read back), the fill of
#          Ready + From-Country-of-work people (committed), the undo record
#          <out>/person_scheme_fill_<db>.csv (one line per created row), DONE line. No restart, no lock
#          needed (data only), refused while another deployer's START is open or a HOLD line stands.
# Undo: Mapping > Who is paid by what > Pay scheme fill > "Undo this fill" (the latest fill of a company),
# or the csv's undo lines in an odoo-bin shell. "Fill empty Country of Work" is never run by this script.
# Root:  bash /odoo/backups/pscheme-p3-<TS>/fill/ps3_fill.sh <db> dry|apply
DB=$1; MODE=$2
HERE=$(cd "$(dirname "$0")" && pwd)
case "$DB" in payobook|payobook_template|p0clone|rize|sudima) ;; *) echo "one of the five databases only (never abm)"; exit 1 ;; esac
case "$MODE" in dry|apply) ;; *) echo "dry or apply"; exit 1 ;; esac
TS=$(date -u +%Y%m%dT%H%MZ)
OUT=$HERE/run-$DB-$MODE-$TS
TAG="Claude PSCHEME fill"
mkdir -p $OUT && chmod 700 $OUT
note() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') | $TAG | $1" >> /opt/deploy-notes.md; }
if [ "$MODE" = apply ]; then
  OPEN=$(python3 - "$TAG" <<'PY'
import sys, datetime, re
tag = sys.argv[1]
lines = open('/opt/deploy-notes.md', encoding='utf-8', errors='replace').read().splitlines()
today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
base = lambda s: s.split('(')[0].strip().lower()
opens, hold = {}, ''
for l in [x for x in lines if x[:10] == today]:
    parts = [p.strip() for p in l.split('|')]
    if len(parts) < 3 or tag in parts[1]:
        continue
    who, what = parts[1], parts[2].upper()
    if what == 'START':
        opens[who] = l
    elif what.startswith(('DONE', 'FAILED', 'VERIFIED', 'ABORTED', 'CANCELLED', 'COMPLETE', 'CALLED OFF')):
        for k in list(opens):
            if k == who or base(k) == base(who):
                opens.pop(k)
    if re.search(r'\bHOLD\b', parts[2], re.I):
        hold = l
print(('HOLD ' + hold[:120]) if hold else (('OPEN ' + list(opens.values())[-1][:120]) if opens else ''))
PY
)
  [ -n "$OPEN" ] && { echo "not now: $OPEN"; exit 1; }
  note "START | one-time pay scheme fill (Give everyone their own pay scheme: Ready + From Country of work) | $DB | data only, no restart | dump $OUT/$DB-before-fill.dump; undo record $OUT/person_scheme_fill_$DB.csv; undo = Mapping > Pay scheme fill > Undo this fill. ABM untouched."
  sudo -u postgres pg_dump -Fc $DB > $OUT/$DB-before-fill.dump && pg_restore -l $OUT/$DB-before-fill.dump > /dev/null \
    || { note "FAILED | fill not run: the dump could not be taken | $DB | nothing changed"; exit 1; }
fi
# the odoo user cannot enter the root-only backup folder: it works in a private temp folder, the results
# are copied next to the dump afterwards
WORK=$(mktemp -d /tmp/ps3fill.XXXXXX); chown odoo:odoo $WORK; chmod 700 $WORK
sed -e "s#^logfile.*#logfile = $WORK/odoo.log#" /etc/odoo-server.conf > $WORK/probe.conf; chown odoo:odoo $WORK/probe.conf; chmod 600 $WORK/probe.conf
cp $HERE/ps3_fill.py $WORK/ && chown odoo:odoo $WORK/ps3_fill.py
sudo -u odoo env PS3_MODE=$MODE PS3_OUT=$WORK python3 /odoo/odoo-server/odoo-bin shell -c $WORK/probe.conf -d $DB --no-http --max-cron-threads=0 < $WORK/ps3_fill.py > $WORK/fill.out 2>&1
rm -f $WORK/probe.conf
cp -a $WORK/. $OUT/ && rm -rf $WORK
grep -E '^PROBE|Traceback' $OUT/fill.out | cut -c1-900
if [ "$MODE" = apply ]; then
  if grep -q '^PROBE committed' $OUT/fill.out; then
    note "DONE | one-time pay scheme fill | $DB | $(grep '^PROBE committed' $OUT/fill.out | sed 's/^PROBE //'); per company: $(python3 -c "import json;d=json.load(open('$OUT/fill-$DB.json'));print('; '.join('company %s: %s people, pending %s' % (c['company'], (c.get('applied') or {}).get('people'), (c.get('applied') or {}).get('pending')) for c in d['companies']))"); undo record $OUT/person_scheme_fill_$DB.csv. ABM untouched."
  else
    note "FAILED | one-time pay scheme fill | $DB | nothing committed (see $OUT/fill.out); dump $OUT/$DB-before-fill.dump. ABM untouched."
  fi
fi
echo "output: $OUT"
