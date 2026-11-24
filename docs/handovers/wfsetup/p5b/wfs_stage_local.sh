#!/bin/bash
# WFSETUP P5b: build the staging tar from a PUSHED commit and copy it and the scripts to the server's /tmp.
# Clone of docstudio/w2/w2_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/wfsetup/p5b/wfs_stage_local.sh <COMMIT> <OUT_DIR>
# pb_attendance_policy ships unchanged (its live tree must already equal the commit; prep says so).
COMMIT=$1; OUT=$2
MODS="pb_workforce_setup pb_workforce_workspace pb_hr_workforce pb_attendance_policy"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/wfs_stage.tar"
tar -xf "$OUT/wfs_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/wfs_mods.txt"
git rev-parse "$COMMIT" > "$OUT/wfs_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/wfs_commit_trees.txt"
D=docs/handovers/wfsetup/p5b
scp -q "$OUT/wfs_stage.tar" "$OUT/wfs_mods.txt" "$OUT/wfs_commit.txt" "$OUT/wfs_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/wfs_commit_trees.txt"
