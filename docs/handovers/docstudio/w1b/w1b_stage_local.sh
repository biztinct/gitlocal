#!/bin/bash
# DOCSTUDIO W1B: build the staging tar from a PUSHED commit and copy it and the scripts to the server's /tmp.
# Clone of w1a/w1a_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/docstudio/w1b/w1b_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_doc_studio"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/w1b_stage.tar"
tar -xf "$OUT/w1b_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/w1b_mods.txt"
git rev-parse "$COMMIT" > "$OUT/w1b_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/w1b_commit_trees.txt"
D=docs/handovers/docstudio/w1b
scp -q "$OUT/w1b_stage.tar" "$OUT/w1b_mods.txt" "$OUT/w1b_commit.txt" "$OUT/w1b_commit_trees.txt" \
    $D/w1b_prep.sh $D/w1b_rehearse.sh $D/w1b_golive.sh $D/w1b_tries.sh $D/w1b_verify.sh \
    $D/w1b_counts.sh $D/w1b_probe.py $D/w1b_golden.py $D/w1b_bundle.py $D/w1b_activity.sh Payobook19v2:/tmp/
cat "$OUT/w1b_commit_trees.txt"
