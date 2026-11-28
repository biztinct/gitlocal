#!/bin/bash
# WFSETUP P9: staging tar of TWO modules (pb_clock, pb_workforce_setup) from a PUSHED commit + the P9
# scripts to the server's /tmp. Clone of ../p6/p6_stage_local.sh; hashes with p9_hashtree.sh (skips
# pb_clock's server-built releases/*.zip, which never ships from the repo and must survive the rsync).
# Run from the worktree root:  bash docs/handovers/wfsetup/p9/p9_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_clock pb_workforce_setup"
set -e
D=docs/handovers/wfsetup/p9
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/p9_stage.tar"
tar -xf "$OUT/p9_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/p9_mods.txt"
git rev-parse "$COMMIT" > "$OUT/p9_commit.txt"
bash $D/p9_hashtree.sh "$OUT/commit" $MODS > "$OUT/p9_commit_trees.txt"
scp -q "$OUT/p9_stage.tar" "$OUT/p9_mods.txt" "$OUT/p9_commit.txt" "$OUT/p9_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/p9_commit_trees.txt"
