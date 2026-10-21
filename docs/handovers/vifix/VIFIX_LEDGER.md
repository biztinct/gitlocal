# VIFIX — conventions and gotcha ledger

Read `VIFIX_PROGRAM.md` first. The LEARNREV ledger (`docs/handovers/learnrev/LEARNREV_LEDGER.md`) still applies,
especially LR17 (AI off on clones), LR20/LR29 (stored translations and the overwrite guard), LR28 (the Learn
generator merges `vi_VN.po`), LR60–LR62 (server jobs and ssh), and LR79 (warm the CSS bundle after a restart).

| Row | Date | Gotcha | Rule |
|---|---|---|---|
| VF1 | 2026-10-21 | Same-text check: 271 msgstr are identical to the English msgid. Some are right (codes, brand names, "OK", "PDF", "Excel"); most are untranslated. | Keep an allowlist of English words that legitimately stay (brand, file types, codes, units); everything else in Latin script on a Vietnamese screen is a finding. |
