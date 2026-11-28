#!/bin/bash
# FS-15: build the staging files from a PUSHED commit and copy them and the scripts to the server's /tmp.
# Run from the repository root: bash docs/handovers/formstudio/fs15/fs15_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_form_studio pb_form_studio_people pb_employee_form_tidy pb_learn"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/fs15_stage.tar"
tar -xf "$OUT/fs15_stage.tar" -C "$OUT/commit"
git archive origin/19.1 $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/fs15_mods.txt"
git rev-parse "$COMMIT" > "$OUT/fs15_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/fs15_commit_trees.txt"
bash "$OUT/s2_hashtree.sh" "$OUT/base" $MODS > "$OUT/fs15_base_trees.txt"
D=docs/handovers/formstudio/fs15
scp -q "$OUT/fs15_stage.tar" "$OUT/fs15_mods.txt" "$OUT/fs15_commit.txt" "$OUT/fs15_commit_trees.txt" \
    "$OUT/fs15_base_trees.txt" $D/fs15_prep.sh $D/fs15_rehearse.sh $D/fs15_golive.sh $D/fs15_tries.sh \
    $D/fs15_verify.sh $D/fs15_after.sh $D/fs15_counts.sh $D/fs15_probe.py Payobook19v2:/tmp/
cat "$OUT/fs15_commit_trees.txt" "$OUT/fs15_base_trees.txt"
