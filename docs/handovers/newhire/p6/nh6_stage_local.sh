#!/bin/bash
# NEWHIRE P6: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../p5b/nh_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/newhire/p6/nh6_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
#   pb_lifecycle, pb_onboarding, pb_assets, pb_training, pb_goals   version bumped (-u on all five)
#   biz_debrand    Python only, no bump (a bump would cascade an upgrade of every module that
#                  depends on it): files + the restart
#   pb_new_hire    unchanged; -i on payobook_template, p0clone, sudima, rize
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_lifecycle pb_onboarding pb_assets pb_training pb_goals biz_debrand pb_new_hire"
set -e
D=docs/handovers/newhire/p6
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/nh6_stage.tar"
tar -xf "$OUT/nh6_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/nh6_mods.txt"
git rev-parse "$COMMIT" > "$OUT/nh6_commit.txt"
bash $D/nh6_hashtree.sh "$OUT/commit" $MODS > "$OUT/nh6_commit_trees.txt"
bash $D/nh6_hashtree.sh "$OUT/base" $MODS > "$OUT/nh6_base_trees.txt"
scp -q "$OUT/nh6_stage.tar" "$OUT/nh6_mods.txt" "$OUT/nh6_commit.txt" "$OUT/nh6_commit_trees.txt" "$OUT/nh6_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/nh6_commit_trees.txt"; echo "base:"; cat "$OUT/nh6_base_trees.txt"
