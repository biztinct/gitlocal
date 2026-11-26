#!/bin/bash
# PSCHEME P3: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../../newhire/p8/nh8_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/pscheme/p3/ps3f2_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
# PSCHEME F2: the two modules of the Mapping wording (both installed on all five).
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_scheme_map pb_formula_studio"
set -e
D=docs/handovers/pscheme/p3
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/ps3f2_stage.tar"
tar -xf "$OUT/ps3f2_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/ps3f2_mods.txt"
git rev-parse "$COMMIT" > "$OUT/ps3f2_commit.txt"
bash $D/ps3_hashtree.sh "$OUT/commit" $MODS > "$OUT/ps3f2_commit_trees.txt"
bash $D/ps3_hashtree.sh "$OUT/base" $MODS > "$OUT/ps3f2_base_trees.txt"
scp -q "$OUT/ps3f2_stage.tar" "$OUT/ps3f2_mods.txt" "$OUT/ps3f2_commit.txt" "$OUT/ps3f2_commit_trees.txt" "$OUT/ps3f2_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/ps3f2_commit_trees.txt"; echo "base:"; cat "$OUT/ps3f2_base_trees.txt"
