#!/bin/bash
# WFSETUP P7: NO files ship (the server trees must already equal origin/19.1). This hashes, from a PUSHED
# commit, every custom module in pb_workforce_setup's dependency closure (list computed on the server by
# p7_closure.sh) and copies the hashes + the P7 scripts to the server's /tmp. Clone of ../p6/p6_stage_local.sh.
# Run from the worktree root:  bash docs/handovers/wfsetup/p7/p7_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
set -e
D=docs/handovers/wfsetup/p7
scp -q $D/p7_closure.sh Payobook19v2:/tmp/
ssh Payobook19v2 'sudo bash /tmp/p7_closure.sh' > "$OUT.mods" || true
rm -rf "$OUT" && mkdir -p "$OUT/commit"
MODS=$(cat "$OUT.mods"); mv "$OUT.mods" "$OUT/p7_mods.txt"
git archive "$COMMIT" $MODS | tar -xf - -C "$OUT/commit"
git rev-parse "$COMMIT" > "$OUT/p7_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/p7_commit_trees.txt"
scp -q "$OUT/p7_mods.txt" "$OUT/p7_commit.txt" "$OUT/p7_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "$(wc -w < "$OUT/p7_mods.txt") modules hashed from $(cat "$OUT/p7_commit.txt")"
