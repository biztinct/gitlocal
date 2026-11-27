#!/bin/bash
# Ship committed custom modules and run the release under the server's deployment lock.
# tools/release.sh <looks|normal|risky> <sync,csv> [upgrade,csv]; +name installs a module.
set -euo pipefail
TIER=${1:?release tier required}; MODS=${2:?module list required}; UP=${3:-$MODS}; HOST=${HOST:-Payobook19v2}
REPO=$(cd "$(dirname "$0")/.." && pwd); cd "$REPO"
case "$TIER" in looks|normal|risky) ;; *) echo "Expected looks, normal or risky" >&2; exit 2;; esac
[ "$TIER" != looks ] || UP=-
[[ "$MODS" =~ ^[a-z][a-z0-9_]*(,[a-z][a-z0-9_]*)*$ ]] || { echo "Invalid module list" >&2; exit 2; }
[[ "$UP" == - || "$UP" =~ ^\+?[a-z][a-z0-9_]*(,\+?[a-z][a-z0-9_]*)*$ ]] || { echo "Invalid upgrade list" >&2; exit 2; }
for entry in ${UP//,/ }; do
  name=${entry#+}
  [[ "$name" == - || ",$MODS," == *",$name,"* ]] || { echo "Upgrade module must be staged: $name" >&2; exit 2; }
done
COMMIT=$(git rev-parse HEAD)
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/pb-release.XXXXXXXX")
trap 'rm -rf -- "$STAGE"' EXIT
# The server checkout is owned by the service account. An unreadable list must fail closed.
STD=$(ssh "$HOST" 'sudo -u odoo git -C /odoo/odoo-server ls-tree -d --name-only HEAD:addons')
[[ -n "$STD" ]] || { echo "Cannot verify the standard addon list" >&2; exit 2; }
for name in ${MODS//,/ }; do
  if grep -Fxq "$name" <<<"$STD"; then echo "Refused standard addon: $name" >&2; exit 2; fi
  src=$name
  [[ -f "$src/__manifest__.py" ]] || src=addons/$name
  [[ -f "$src/__manifest__.py" ]] || { echo "Missing module: $name" >&2; exit 2; }
  git diff --quiet HEAD -- "$src" || { echo "Commit the changes in $src before release" >&2; exit 2; }
  mkdir "$STAGE/$name"
  git archive "$COMMIT:$src" | tar -x -C "$STAGE/$name"
done
git diff --quiet HEAD -- ops/pb_release.sh ops/joining tools/release.sh || { echo "Commit release tool changes first" >&2; exit 2; }
mkdir "$STAGE/.release"
git archive "$COMMIT:ops" pb_release.sh joining | tar -x -C "$STAGE/.release"
RUN="pbrel-$(date -u +%Y%m%d-%H%M%S)-$$"
ssh "$HOST" "umask 077 && mkdir /tmp/$RUN-stage"
rsync -az "$STAGE/" "$HOST:/tmp/$RUN-stage/"
ssh "$HOST" "sudo chown -R root:root /tmp/$RUN-stage && sudo install -D -m 755 /tmp/$RUN-stage/.release/pb_release.sh /odoo/ops/pb_release.sh"
args=(sudo systemd-run --collect "--unit=$RUN" "--setenv=WHO=${WHO:-Claude}" "--setenv=COMMIT=$COMMIT" "--setenv=BACKUP=${BACKUP:-nightly}" "--setenv=FRESH_DBS=${FRESH_DBS:-}")
if [[ -n "${DBS:-}" ]]; then args+=("--setenv=DBS=$DBS"); fi
args+=(/bin/bash /odoo/ops/pb_release.sh "$TIER" "/tmp/$RUN-stage" "$MODS" "$UP" "/tmp/$RUN")
printf -v remote '%q ' "${args[@]}"
ssh "$HOST" "$remote"
echo "Running $RUN (tier $TIER, commit $COMMIT)"
ssh "$HOST" "while ! sudo test -f /tmp/$RUN/done; do systemctl is-active --quiet $RUN || { sudo test -f /tmp/$RUN/done || { echo 'Release unit stopped without a result'; exit 1; }; }; sleep 4; done; sudo grep -E 'STEP|backup|upgrade|crons|warm|version|ROLLED|redaction' /tmp/$RUN/run.log; result=\$(sudo cat /tmp/$RUN/result); echo RESULT: \$result; test \"\$result\" = OK"
