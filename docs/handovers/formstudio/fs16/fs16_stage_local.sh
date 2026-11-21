#!/bin/bash
# FS-16: build the staging files from a PUSHED commit and copy them and the scripts to the server's /tmp.
# Run from the repository root: bash docs/handovers/formstudio/fs16/fs16_stage_local.sh <COMMIT> <OUT_DIR>
COMMIT=$1; OUT=$2
MODS="pb_hr_payroll_vietnam pb_employee_form_tidy pb_form_studio_people pb_people_advanced pb_bank_ocr pb_employee_bank_panel"
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/fs16_stage.tar"
tar -xf "$OUT/fs16_stage.tar" -C "$OUT/commit"
git archive origin/19.1 $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/fs16_mods.txt"
git rev-parse "$COMMIT" > "$OUT/fs16_commit.txt"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/fs16_commit_trees.txt"
bash "$OUT/s2_hashtree.sh" "$OUT/base" $MODS > "$OUT/fs16_base_trees.txt"
D=docs/handovers/formstudio/fs16
scp -q "$OUT/fs16_stage.tar" "$OUT/fs16_mods.txt" "$OUT/fs16_commit.txt" "$OUT/fs16_commit_trees.txt" \
    "$OUT/fs16_base_trees.txt" $D/fs16_prep.sh $D/fs16_rehearse.sh $D/fs16_golive.sh $D/fs16_tries.sh \
    $D/fs16_verify.sh $D/fs16_after.sh $D/fs16_counts.sh $D/fs16_probe.py $D/fs16_files.py $D/fs16_reproof.sql Payobook19v2:/tmp/
cat "$OUT/fs16_commit_trees.txt" "$OUT/fs16_base_trees.txt"
