#!/bin/bash
# DOCSTUDIO PDFFIX: compare the old-engine and new-engine PDFs of one database (run where poppler
# is installed). Usage: pdffix_compare.sh <folder holding old/ and new/> [png-out-folder]
# Prints one row per document per engine: pages, bytes, fonts embedded, characters of text,
# page-number lines, "Printed on" lines. Draws page 1 (and the middle page when > 2 pages).
D=$1; PNG=${2:-}
printf '%-34s %-4s %5s %9s %5s %7s %6s %7s\n' document eng pages bytes fonts chars pageno printed
for f in $(ls $D/old/*.pdf $D/new/*.pdf 2>/dev/null | xargs -n1 basename | sort -u); do
  for eng in old new; do
    x=$D/$eng/$f; [ -f "$x" ] || { printf '%-34s %-4s missing\n' $f $eng; continue; }
    pages=$(pdfinfo "$x" 2>/dev/null | awk '/^Pages:/{print $2}')
    bytes=$(wc -c < "$x" | tr -d ' ')
    fonts=$(pdffonts "$x" 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
    txt=$(pdftotext -layout "$x" - 2>/dev/null)
    chars=$(printf '%s' "$txt" | tr -d '[:space:]' | wc -m | tr -d ' ')
    pn=$(printf '%s\n' "$txt" | grep -c -E '(Page|Trang|Halaman) *[0-9]+ *(of|/|trên|dari) *[0-9]+|^ *[0-9]+ */ *[0-9]+ *$')
    pr=$(printf '%s\n' "$txt" | grep -c -E 'Printed on|In lúc|In ngày|Dicetak')
    printf '%-34s %-4s %5s %9s %5s %7s %6s %7s\n' $f $eng "$pages" $bytes $fonts $chars $pn $pr
    if [ -n "$PNG" ]; then
      mkdir -p $PNG; b=${f%.pdf}
      pdftoppm -r 50 -png -f 1 -l 1 "$x" $PNG/${b}_${eng}_p1 >/dev/null 2>&1
      if [ "${pages:-0}" -gt 2 ]; then m=$(( (pages + 1) / 2 )); pdftoppm -r 50 -png -f $m -l $m "$x" $PNG/${b}_${eng}_mid >/dev/null 2>&1; fi
    fi
  done
done
