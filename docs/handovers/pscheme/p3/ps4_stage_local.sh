#!/bin/bash
# PSCHEME P3: staging tar of the shipped modules from a PUSHED commit, the trees of the BASE commit
# (19.1 before this phase: what the server must hold today) + these scripts to the server's /tmp.
# Clone of ../../newhire/p8/nh8_stage_local.sh. Run from the worktree root:
#   bash docs/handovers/pscheme/p3/ps4_stage_local.sh <COMMIT> <BASE_COMMIT> <OUT_DIR>
# PSCHEME P4: Usual pay scheme by country (pb_scheme_map) and its lesson sentence (pb_learn).
COMMIT=$1; BASE=$2; OUT=$3
MODS="pb_scheme_map pb_learn"
set -e
D=docs/handovers/pscheme/p3
rm -rf "$OUT" && mkdir -p "$OUT/commit" "$OUT/base"
git archive "$COMMIT" $MODS > "$OUT/ps4_stage.tar"
tar -xf "$OUT/ps4_stage.tar" -C "$OUT/commit"
git archive "$BASE" $MODS | tar -x -C "$OUT/base"
echo "$MODS" > "$OUT/ps4_mods.txt"
git rev-parse "$COMMIT" > "$OUT/ps4_commit.txt"
bash $D/ps3_hashtree.sh "$OUT/commit" $MODS > "$OUT/ps4_commit_trees.txt"
bash $D/ps3_hashtree.sh "$OUT/base" $MODS > "$OUT/ps4_base_trees.txt"
scp -q "$OUT/ps4_stage.tar" "$OUT/ps4_mods.txt" "$OUT/ps4_commit.txt" "$OUT/ps4_commit_trees.txt" "$OUT/ps4_base_trees.txt" \
  $D/*.sh $D/*.py Payobook19v2:/tmp/
echo "commit:"; cat "$OUT/ps4_commit_trees.txt"; echo "base:"; cat "$OUT/ps4_base_trees.txt"
