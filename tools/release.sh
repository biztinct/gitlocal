#!/bin/bash
# release.sh — one command from your Mac:  tools/release.sh <looks|normal|risky> <modules,csv> [upgrade,csv]
#   upgrade list defaults to the module list; prefix + to install a new module (+pb_new).
#   env: BACKUP=nightly|fresh|none   FRESH_DBS="rize"   DBS="payobook"   HOST=Payobook19v2
# Stages a clean copy, refuses standard Odoo addons, ships it, runs ops/pb_release.sh detached
# on the server, waits, prints the step timings. The server script writes the START/DONE notes.
set -eu
TIER="$1"; MODS="$2"; UP="${3:-$MODS}"; HOST="${HOST:-Payobook19v2}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
RUN="pbrel-$(date -u +%Y%m%d-%H%M%S)"
case "$TIER" in looks|normal|risky) ;; *) echo "tier must be looks|normal|risky"; exit 2;; esac
[ "$TIER" = looks ] && UP="-"
# standard Odoo addons must never be deployed from this repo
STD="$(ssh "$HOST" 'git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u')"
for m in ${MODS//,/ }; do
  [ -d "addons/$m" ] || [ -d "$m" ] || { echo "no such module in repo: $m"; exit 2; }
  echo "$STD" | grep -qx "$m" && { echo "REFUSED: $m is a standard addon (server copy wins)"; exit 2; }
done
SRC=.; [ -d addons ] && SRC=addons
COMMIT="$(git rev-parse --short HEAD)"
git diff --quiet HEAD -- $(for m in ${MODS//,/ }; do echo "$SRC/$m"; done) || echo "WARNING: uncommitted changes in these modules — deploying the working copy, not commit $COMMIT"
ssh "$HOST" "sudo rm -rf /tmp/$RUN-stage && mkdir -p /tmp/$RUN-stage"
for m in ${MODS//,/ }; do rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.DS_Store "$SRC/$m" "$HOST:/tmp/$RUN-stage/"; done
scp -q ops/pb_release.sh "$HOST:/tmp/$RUN-pb_release.sh"
ssh "$HOST" "sudo install -D -m 755 /tmp/$RUN-pb_release.sh /odoo/ops/pb_release.sh"
ENVS="--setenv=WHO=${WHO:-Claude} --setenv=COMMIT=$COMMIT --setenv=BACKUP=${BACKUP:-nightly} --setenv=FRESH_DBS=${FRESH_DBS:-}"
[ -n "${DBS:-}" ] && ENVS="$ENVS --setenv=DBS=$DBS"
ssh "$HOST" "sudo systemd-run --collect --unit=$RUN $ENVS /bin/bash /odoo/ops/pb_release.sh $TIER /tmp/$RUN-stage $MODS $UP /tmp/$RUN"
echo "running as $RUN (tier $TIER, commit $COMMIT) ..."
ssh "$HOST" "until test -f /tmp/$RUN/done; do sleep 4; done; echo RESULT: \$(cat /tmp/$RUN/result); grep -E 'STEP|backup|upgrade|crons|warm|version|ROLLED' /tmp/$RUN/run.log"
