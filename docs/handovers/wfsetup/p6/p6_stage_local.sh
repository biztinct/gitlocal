#!/bin/bash
# WFSETUP P6: staging tar of ONE module from a PUSHED commit + the P6 scripts to the server's /tmp.
# Trimmed clone of ../p5b/wfs_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/wfsetup/p6/p6_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_workforce_setup"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/p6_stage.tar"
tar -xf "$OUT/p6_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/p6_mods.txt"
git rev-parse "$COMMIT" > "$OUT/p6_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/p6_commit_trees.txt"
D=docs/handovers/wfsetup/p6
scp -q "$OUT/p6_stage.tar" "$OUT/p6_mods.txt" "$OUT/p6_commit.txt" "$OUT/p6_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/p6_commit_trees.txt"
