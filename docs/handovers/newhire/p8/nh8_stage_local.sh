#!/bin/bash
# NEWHIRE P8: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../p6/nh6_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/newhire/p8/nh8_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
#   pb_new_hire, pb_form_studio_portal   version bumped (-u on all five; two new roles, templates, .po)
#   pb_scheme_map, biz_access            Python + static + .po, no bump: files + the restart + asset purge
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_new_hire pb_form_studio_portal pb_scheme_map biz_access"
set -e
D=docs/handovers/newhire/p8
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/nh8_stage.tar"
tar -xf "$OUT/nh8_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/nh8_mods.txt"
git rev-parse "$COMMIT" > "$OUT/nh8_commit.txt"
bash $D/nh8_hashtree.sh "$OUT/commit" $MODS > "$OUT/nh8_commit_trees.txt"
bash $D/nh8_hashtree.sh "$OUT/base" $MODS > "$OUT/nh8_base_trees.txt"
scp -q "$OUT/nh8_stage.tar" "$OUT/nh8_mods.txt" "$OUT/nh8_commit.txt" "$OUT/nh8_commit_trees.txt" "$OUT/nh8_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/nh8_commit_trees.txt"; echo "base:"; cat "$OUT/nh8_base_trees.txt"
