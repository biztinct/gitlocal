#!/bin/sh
# Inline src/core.js into each option page so every POC is one self-contained file.
cd "$(dirname "$0")"
for o in a b c d; do
  awk -v core="src/core.js" '
    /<!--@core-->/ { print "<script>"; while ((getline l < core) > 0) print l; close(core); print "</script>"; next }
    { print }' "src/option_$o.html" > "option_$o.html"
done
echo built: option_a.html option_b.html option_c.html option_d.html
