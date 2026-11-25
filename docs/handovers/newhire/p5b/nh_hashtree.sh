#!/bin/bash
# NEWHIRE P5b (copy of ../../wfsetup/p10b/p10b_hashtree.sh) - copy of /tmp/s2_hashtree.sh that also skips releases/*.zip (pb_clock's gitignored, server-built
# connector download, a known runtime artifact - tools/workforce_workspace/prepare_release.py:22).
# usage: nh_hashtree.sh <root> <module>...  -> "<module> <version> <hash of sorted file md5s>"
# portable: uses md5sum when present, else `md5 -r` (macOS)
root=$1; shift
if command -v md5sum >/dev/null 2>&1; then M="md5sum"; else M="md5 -r"; fi
for m in "$@"; do
  if [ -d "$root/$m" ]; then
    h=$(cd "$root/$m" && find . -type f ! -name '*.pyc' ! -path '*/__pycache__/*' ! -name '.DS_Store' ! -path './releases/*.zip' | LC_ALL=C sort | while read -r f; do $M "$f" | awk '{print $1}'; echo "$f"; done | $M | cut -c1-12)
    v=$(python3 -c "import ast;print(ast.literal_eval(open('$root/$m/__manifest__.py').read()).get('version'))")
    echo "$m $v $h"
  else
    echo "$m ABSENT"
  fi
done
