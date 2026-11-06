# LEARN REFRESH — Step 3: new lessons for payroll setup

Read first: `LEARN_REFRESH_LEDGER.md` (binding, incl. the Step 1 and Step 2 report
sections appended to it) and `FACTS_STEP3_SETUP.md` (verified labels/flows — use them;
re-check only where the code moved). Do not re-derive.

## Scope — six new stations on the map (line `setup`), each a FULL lesson

| Key | Name on the map | Where it lives | Hero flow taught |
|---|---|---|---|
| blueprint | New configuration | Settings › Guided setup (and a scheme's Settings) | Start → Pay rules → Connect → Outputs → Test → Finish; the live pay panel; finish ≠ switch on; edit mode + proposals |
| mapping | Mapping | Settings › Integrations › Mapping | Journey read-through; Excel on-ramp; sources in priority order ("a lower source only fills an empty box"); "From this pay run"; conflict dialog; Who is paid by what |
| treatment | Component treatment | Mapping › Component treatment | pay role decides net arithmetic; subtotal; value types; Re-classify; why "These figures do not add up" sends you here; recompute after saving |
| matrix | Approval Matrix | Settings › Approvals | read a route; builder Purpose→Publish; No approval needed (still recorded); People & backups / cover; per-scheme choice; publish affects new requests only |
| records | Records Desk | People › Records (+ Bulk update, run wizard, Mapping) | only mapped fields; export→edit→import round trip; Review; approval + Undo |
| schemes | Schemes and currencies | Settings › Group + Pay Run › Run + Insights › Explorer | a scheme pays in its country's money; a pay run is per scheme; two schemes one month; exchange-rate policy; nothing stored converted; Compare schemes |

Each station: what / why / when / prerequisites / common mistakes / 5–9 steps /
check-yourself question(s) / glossary terms / role tags (officer, hr, approver,
owner — step 5 finalises paths) / `places` for the helper (step 1 mechanism) /
duration. EN + VI.

**Practice company screens.** Add replica screens (fixture + screens.js, same shell
built in step 2) for the hero flow of blueprint (Start + Pay rules + live pay panel),
mapping (Journey board), matrix (Matrix grid + builder), records (desk + review). Keep
them compact: one replica screen per station, driven by fixture data for Hoa Sen
Retail Co.; numbers derived via practice-data.js where money is shown. treatment and
schemes may reuse existing replica screens + a small panel, or teach on the real app
only — decide and say why.

**Real-app walkthroughs (scenarios).** One Watch walkthrough per station on the real
app. The product screens have NO anchors: add `data-coach` anchors in the product
templates (prefixes: `bp-` blueprint, `mp-` mapping, `ct-` treatment, `am-` matrix,
`rd-` records, `gp-` group) on stable elements that render in the embedded/hub mode,
register them in anchors.json (test 01/05 must stay green). Add them to the
`pb_hub_palette` ⌘K rows (step 1/v3 mechanism reads content — confirm the rows appear).
Retire sc_mapping (step 2 hid it) by replacing it with the new Mapping walkthrough
under a NEW key (keep old progress rows harmless).

**Helper + Ask Payobook.** Map `places` so the helper's Guide me on each of these
screens shows the lesson (not the hub orientation). Add intents: "how do I set up a new
pay scheme", "where does this number come from" (mapping sources), "why don't my
figures add up" (treatment), "who approves X / change an approval route" (matrix),
"change many employees at once" (records), "pay people in another currency" (schemes).
Extend Ask Payobook's product prompt (step 2 rewrote it) with one short paragraph per
area + the new lesson keys in its whitelist.

**Glossary:** Guided setup, Starter, Sample employee, Check (test), Proposal, Source,
Source priority, Transformation, Journey (mapping), Component treatment, Pay role,
Subtotal, Value type, Approval route (exists from step 2 — extend), Responsibility,
Cover, Records Desk, Exchange rate policy, Group currency.

## Non-goals
No product behaviour changes except adding anchors. No role-path/chapter redo (step 5)
— but new stations must appear in a chapter so they are visible: put them in the
existing setup chapter (ch3) for now. Don't touch step-4 areas.

## Design
Bar (verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."**
Hero moment: **the Mapping lesson's Journey board lights up lane by lane** — Files &
systems → Feeds → Transformations → Scheme — with a single value (Mai's basic salary)
travelling the wire into her payslip line; in the Blueprint lesson the "See it in
someone's pay" number ticks as a component is added. Zero dead-ends, plain words,
motion with purpose, phone width, Lucide only.

## Test cases
1. Each new station opens from the map, all steps play, replica anchors resolve.
2. Each new Watch walkthrough on payobook.com (demo login) — every step anchored; none
   leaves anything changed (walkthroughs never save).
3. Try mode for the four replica-backed stations.
4. Helper Guide me on each real screen → the right lesson.
5. ⌘K finds each lesson and walkthrough by a natural word ("currency", "approval route",
   "bulk update", "mapping").
6. Ask Payobook: the six new questions → correct answer + hand-off.
7. Contract checker 0 failures; anchor tests green; jargon / replay / resolver /
   scenario tools green (add resolver cases for the new intents).
8. pb_learn suite + suites of every module you added anchors to, on a throwaway clone.
9. VI walk for 2 lessons; no English leaks.
10. Phone width; console clean.

## Deploy
pb_learn + every module that got anchors (blueprint, formula studio, scheme map,
approval config, records, group, explorer if touched) + pb_payroll_ai_insights. Tier:
normal. All 4 DBs; restart after purge.

## Report back
Per station: built / replica or real-only / anchors added; tests 1–10; self-score vs the
bar; ledger LR* additions; commits; versions per DB; any product behaviour contradicting
a lesson (list, don't fix).
