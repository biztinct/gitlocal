#!/bin/bash
# DOCSTUDIO W1A: build the staging tar from a PUSHED commit and copy it and the scripts to the server's /tmp.
# Run from the worktree root: bash docs/handovers/docstudio/w1a/w1a_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_explorer pb_report_builder pb_excel_layout"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/w1a_stage.tar"
tar -xf "$OUT/w1a_stage.tar" -C "$OUT/commit"
git archive "$BASE" pb_explorer | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/w1a_mods.txt"
git rev-parse "$COMMIT" > "$OUT/w1a_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/w1a_commit_trees.txt"
bash "$OUT/s2_hashtree.sh" "$OUT/base" $MODS > "$OUT/w1a_base_trees.txt"
D=docs/handovers/docstudio/w1a
scp -q "$OUT/w1a_stage.tar" "$OUT/w1a_mods.txt" "$OUT/w1a_commit.txt" "$OUT/w1a_commit_trees.txt" \
    "$OUT/w1a_base_trees.txt" $D/w1a_prep.sh $D/w1a_rehearse.sh $D/w1a_golive.sh $D/w1a_tries.sh \
    $D/w1a_verify.sh $D/w1a_counts.sh $D/w1a_probe.py $D/w1a_activity.sh Payobook19v2:/tmp/
cat "$OUT/w1a_commit_trees.txt" "$OUT/w1a_base_trees.txt"
