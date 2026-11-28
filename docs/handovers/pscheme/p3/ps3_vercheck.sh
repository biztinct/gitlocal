#!/bin/bash
# PSCHEME P3: every shipped module installed at its manifest version on <db>? (19.0. prefix normalised)
# usage: ps3_vercheck.sh <db> <trees file: "module version hash">  -> "ok" or the mismatches
db=$1; trees=$2
norm() { echo "$1" | sed -E 's/^19\.0\.//'; }
bad=""
while read -r m v h; do
  st=$(sudo -u postgres psql -X -At -d $db -c "select state||'|'||coalesce(latest_version,'') from ir_module_module where name='$m'")
  if [ "${st%%|*}" != installed ] || [ "$(norm ${st#*|})" != "$(norm $v)" ]; then bad="$bad $m(manifest $v, db ${st:-none})"; fi
done < $trees
echo "${bad:-ok}"
