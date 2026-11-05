# PDR — closeout (2026-11-06)

All three phases are live on payobook, payobook_template, p0clone and rize.
Reports: `PDR_P1_REPORT.md`, `PDR_P2_REPORT.md`, `PDR_P3_REPORT.md`. Ledger
gotchas G1–G27 are in `PDR_LEDGER.md`.

| | Before (2026-11-05) | After |
|---|---|---|
| Open Indonesia "Review pay data" (113 people) | 49 s | 10.6 s |
| Save one cell | 52 s | ~12 s |
| Formula preview per person | 8.8 s | 0.03 s |
| Red cells on prep #19 | 1,240 | 1 (real) |
| Yes/no flags on screen / in the file | 1 / 0 | Yes / No, Y / N, words |
| Full contract form save without HR Responsible | refused | allowed |
| Pay package from contract | flags became earnings | flags skipped |

Undo for the rize data steps: `PDR_P1_REPORT.md` (`pb_bak_pdr_zero_20261105`)
and `PDR_P2_REPORT.md` (`pb_bak_pdr_words_20261105`).

## Open items

1. **Speed past 10.6 s** needs the older employee/contract value reader
   (`_get_formula_input_values` chain, ~35 % of the open). Owner: "good enough
   for now" (2026-11-05). Revisit if Rize's headcount grows.
2. **Still showing numbers** (no yes/no flag is on a payslip today):
   - the payslip PDF: `payslip_themed.xml:109-110`; it would also add a flag
     into a subtotal
   - the portal payslip: `pb_me_portal portal_templates.xml:609`
   - the source journey screen: `pb_source_atlas atlas.xml:319`
   - the contract change history: `contract_component_change_views.xml`
   - the Records Desk cell while it is being edited
3. **The sudima tenant** was created 2026-11-05 13:21 UTC by another session.
   It has the P3 files but has not been upgraded, so F1 is not active there.
4. **payobook demo package 5:**
   - `TYLETAMHQCV` = 1 (a yes/no line from before F2), left unchanged under
     the keep-demo-data rule.
   - `NPT` (number of dependants) = 3 is typed as money, so F2 cannot catch
     it. The rule's setting needs fixing.
5. **Translations:** Vietnamese is done for the worksheet sentences. Check the
   `pb_payroll_templates` messages for Vietnamese at the next translation pass.
