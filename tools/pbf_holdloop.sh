#!/bin/bash
# Runs UNDER the preview lock (flock hands it this script): records the holder
# and keeps the lock until `release` removes the holder file or another holder
# replaces it. Started detached by pbf_preview.sh hold.
P=/tmp/pbf_preview
who="$1"
echo "$who $(date -u +%H:%M)" > "$P/holder"
touch "$P/held.$who"
while [ -f "$P/holder" ] && grep -q "^$who " "$P/holder"; do sleep 5; done
rm -f "$P/held.$who"
