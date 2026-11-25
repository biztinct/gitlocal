#!/bin/bash
# WFSETUP P10b: staging tar of seven modules (pb_clock, pb_workforce_setup) from a PUSHED commit + the P9
# scripts to the server's /tmp. Clone of ../p6/p6_stage_local.sh; hashes with p10b_hashtree.sh (skips
# pb_clock's server-built releases/*.zip, which never ships from the repo and must survive the rsync).
# Run from the worktree root:  bash docs/handovers/wfsetup/p9/p10b_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_hr_payroll_formula pb_clock pb_attendance_policy pb_payrun_wizard pb_workforce_setup pb_formula_studio pb_blueprint"
set -e
D=docs/handovers/wfsetup/p10b
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/p10b_stage.tar"
tar -xf "$OUT/p10b_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/p10b_mods.txt"
git rev-parse "$COMMIT" > "$OUT/p10b_commit.txt"
bash $D/p10b_hashtree.sh "$OUT/commit" $MODS > "$OUT/p10b_commit_trees.txt"
scp -q "$OUT/p10b_stage.tar" "$OUT/p10b_mods.txt" "$OUT/p10b_commit.txt" "$OUT/p10b_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/p10b_commit_trees.txt"
