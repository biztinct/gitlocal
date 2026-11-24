#!/bin/bash
# DOCSTUDIO W2: build the staging tar from a PUSHED commit and copy it and the scripts to the server's /tmp.
# Clone of w1b/w1b_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/docstudio/w2/w2_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_doc_studio pb_doc_studio_hiring pb_doc_studio_me pb_doc_contracts pb_report_pdf pb_report_pdf_send pb_report_builder pb_explorer"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit"
git archive "$COMMIT" $MODS > "$OUT/w2_stage.tar"
tar -xf "$OUT/w2_stage.tar" -C "$OUT/commit"
echo "$MODS" > "$OUT/w2_mods.txt"
git rev-parse "$COMMIT" > "$OUT/w2_commit.txt"
git show "$COMMIT:docs/handovers/docstudio/a1/golden.py" > "$OUT/w2_golden_a1.py"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/w2_commit_trees.txt"
D=docs/handovers/docstudio/w2
scp -q "$OUT/w2_stage.tar" "$OUT/w2_mods.txt" "$OUT/w2_commit.txt" "$OUT/w2_commit_trees.txt" "$OUT/w2_golden_a1.py" \
    $D/w2_prep.sh $D/w2_rehearse.sh $D/w2_golive.sh $D/w2_tries.sh $D/w2_verify.sh \
    $D/w2_counts.sh $D/w2_probe.py $D/w2_golden.py $D/w2_bundle.py $D/w2_activity.sh Payobook19v2:/tmp/
cat "$OUT/w2_commit_trees.txt"
