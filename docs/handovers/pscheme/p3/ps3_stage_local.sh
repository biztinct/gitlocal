#!/bin/bash
# PSCHEME P3: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../../newhire/p8/nh8_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/pscheme/p3/ps3_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
# All eleven are installed on all five databases and all are -u'd (versions bumped or files changed).
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_scheme_map pb_hr_payroll_formula pb_contracts pb_import_batch pb_import_wizard pb_job_change pb_new_hire pb_pay_package pb_payrun_wizard pb_updates pb_learn"
set -e
D=docs/handovers/pscheme/p3
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/ps3_stage.tar"
tar -xf "$OUT/ps3_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/ps3_mods.txt"
git rev-parse "$COMMIT" > "$OUT/ps3_commit.txt"
bash $D/ps3_hashtree.sh "$OUT/commit" $MODS > "$OUT/ps3_commit_trees.txt"
bash $D/ps3_hashtree.sh "$OUT/base" $MODS > "$OUT/ps3_base_trees.txt"
scp -q "$OUT/ps3_stage.tar" "$OUT/ps3_mods.txt" "$OUT/ps3_commit.txt" "$OUT/ps3_commit_trees.txt" "$OUT/ps3_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/ps3_commit_trees.txt"; echo "base:"; cat "$OUT/ps3_base_trees.txt"
