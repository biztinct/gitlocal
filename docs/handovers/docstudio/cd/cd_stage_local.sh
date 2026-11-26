#!/bin/bash
# DOCSTUDIO close-out D: build the staging tar from a PUSHED commit (that contains current
# origin/19.1) and copy it + the scripts to the server's /tmp. Run from the worktree root:
#   bash docs/handovers/docstudio/cd/cd_stage_local.sh <COMMIT> <BASE_19.1_COMMIT> <OUT_DIR>
# BASE = the origin/19.1 commit merged in: the live trees must equal its trees before go-live
# (nobody shipped something newer in between).
COMMIT=$1; BASE=$2; OUT=$3
D=docs/handovers/docstudio/cd
MODS=$(cat $D/cd_mods.txt)
set -e
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/cd_stage.tar"
tar -xf "$OUT/cd_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -xf - -C "$OUT/base"
echo "$MODS" > "$OUT/cd_mods.txt"
git rev-parse "$COMMIT" > "$OUT/cd_commit.txt"
git show "$COMMIT:docs/handovers/docstudio/a1/golden.py" > "$OUT/cd_golden_a1.py"
git show "$COMMIT:docs/handovers/docstudio/w2/w2_golden.py" > "$OUT/cd_golden_f.py"
scp -q Payobook19v2:/tmp/s2_hashtree.sh "$OUT/s2_hashtree.sh"
bash "$OUT/s2_hashtree.sh" "$OUT/commit" $MODS > "$OUT/cd_commit_trees.txt"
bash "$OUT/s2_hashtree.sh" "$OUT/base" $MODS > "$OUT/cd_base_trees.txt"
scp -q "$OUT/cd_stage.tar" "$OUT/cd_mods.txt" "$OUT/cd_commit.txt" "$OUT/cd_commit_trees.txt" "$OUT/cd_base_trees.txt" \
    "$OUT/cd_golden_a1.py" "$OUT/cd_golden_f.py" \
    $D/cd_prep.sh $D/cd_rehearse.sh $D/cd_golive.sh $D/cd_tries.sh $D/cd_verify.sh $D/cd_counts.sh \
    $D/cd_probe.py $D/cd_bundle.py $D/cd_golden_cmp.py $D/cd_states.sh Payobook19v2:/tmp/
echo "== commit trees"; cat "$OUT/cd_commit_trees.txt"; echo "== base (origin/19.1) trees"; cat "$OUT/cd_base_trees.txt"
