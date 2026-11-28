#!/bin/bash
# NEWHIRE P7: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../p6/nh6_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/newhire/p7/nh7_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
#   pb_bank_ocr, pb_me_details, pb_new_hire   version bumped (-u on all five; new stored fields, views, .po)
#   pb_people_advanced, pb_scheme_map         Python only, no bump: files + the restart
#   pb_learn                                  static files only (lesson JSON, replica), no bump: files + asset purge
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_bank_ocr pb_me_details pb_new_hire pb_people_advanced pb_scheme_map pb_learn"
set -e
D=docs/handovers/newhire/p7
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/nh7_stage.tar"
tar -xf "$OUT/nh7_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/nh7_mods.txt"
git rev-parse "$COMMIT" > "$OUT/nh7_commit.txt"
bash $D/nh7_hashtree.sh "$OUT/commit" $MODS > "$OUT/nh7_commit_trees.txt"
bash $D/nh7_hashtree.sh "$OUT/base" $MODS > "$OUT/nh7_base_trees.txt"
scp -q "$OUT/nh7_stage.tar" "$OUT/nh7_mods.txt" "$OUT/nh7_commit.txt" "$OUT/nh7_commit_trees.txt" "$OUT/nh7_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/nh7_commit_trees.txt"; echo "base:"; cat "$OUT/nh7_base_trees.txt"
