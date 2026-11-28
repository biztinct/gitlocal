#!/bin/bash
# WFSETUP P10c: staging tar of the two changed modules from a PUSHED commit + the P10c scripts to the
# server's /tmp. Clone of ../p10b/p10b_stage_local.sh.
# Run from the worktree root:  bash docs/handovers/wfsetup/p10c/p10c_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_hr_payroll_formula pb_formula_studio"
set -e
D=docs/handovers/wfsetup/p10c
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/p10c_stage.tar"
tar -xf "$OUT/p10c_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/p10c_mods.txt"
git rev-parse "$COMMIT" > "$OUT/p10c_commit.txt"
for M in $MODS; do echo -n "$M $(python3 -c "import ast;print(ast.literal_eval(open('$OUT/commit/$M/__manifest__.py').read())['version'])"), "; done | sed 's/, $//' > "$OUT/p10c_versions.txt"
bash $D/p10c_hashtree.sh "$OUT/commit" $MODS > "$OUT/p10c_commit_trees.txt"
scp -q "$OUT/p10c_stage.tar" "$OUT/p10c_mods.txt" "$OUT/p10c_commit.txt" "$OUT/p10c_commit_trees.txt" "$OUT/p10c_versions.txt" $D/*.sh $D/*.py Payobook19v2:/tmp/
cat "$OUT/p10c_commit_trees.txt" "$OUT/p10c_versions.txt"
