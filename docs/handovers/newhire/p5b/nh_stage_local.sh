#!/bin/bash
# NEWHIRE P5b: staging tar of the six shipped modules from a PUSHED commit + these scripts to the
# server's /tmp. Clone of ../../wfsetup/p10b/p10b_stage_local.sh.
# Run from the worktree root:  bash docs/handovers/newhire/p5b/nh_stage_local.sh <COMMIT> <OUT_DIR>
#   pb_new_hire            new (installed on payobook only)
#   pb_learn, pb_people    version bumped (-u on all five)
#   pb_hr_payroll_formula, pb_probation, pb_scheme_map
#                          Python-only factor-outs, no version bump (files + the restart)
COMMIT=$1; OUT=$2
MODS="pb_new_hire pb_learn pb_people pb_hr_payroll_formula pb_probation pb_scheme_map"
set -e
D=docs/handovers/newhire/p5b
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/nh_stage.tar"
tar -xf "$OUT/nh_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/nh_mods.txt"
git rev-parse "$COMMIT" > "$OUT/nh_commit.txt"
bash $D/nh_hashtree.sh "$OUT/commit" $MODS > "$OUT/nh_commit_trees.txt"
scp -q "$OUT/nh_stage.tar" "$OUT/nh_mods.txt" "$OUT/nh_commit.txt" "$OUT/nh_commit_trees.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/nh_commit_trees.txt"
