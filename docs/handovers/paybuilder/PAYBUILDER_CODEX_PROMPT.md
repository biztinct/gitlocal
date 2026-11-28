# Prompt to paste into the coding session

```
You are building a feature called the PAY BUILDER for Payobook (an HR + payroll product built as custom
Odoo 19 modules). The design is finished and approved by the owner. Your job is to build it exactly as
designed, test it, release it, and report back. Ask me only if something in the design pack is contradictory
or impossible; otherwise decide, note the decision in your report, and keep going.

REPOSITORY
- Main checkout: /Users/adity/Documents/GitHub/gitlocal (branch 19.1). DO NOT build there: it is about 180
  commits behind origin/19.1 and has unrelated uncommitted files.
- Create a fresh worktree from origin/19.1 on a new branch `paybuilder` and do all work there:
    cd /Users/adity/Documents/GitHub/gitlocal && git fetch origin 19.1
    git worktree add ../gitlocal-worktrees/paybuilder -b paybuilder origin/19.1
- Copy the design pack into the worktree and commit it first ("PAYBUILDER docs: design pack"):
    /Users/adity/Documents/GitHub/gitlocal/docs/handovers/paybuilder/   (all files)
    /Users/adity/Documents/GitHub/gitlocal/docs/design/pay-builder-poc.html

READ THESE FIRST, IN THIS ORDER (they are the whole brief)
1. docs/handovers/paybuilder/PAYBUILDER_LEDGER.md          rules, rulings and gotchas that bind everything
2. docs/handovers/paybuilder/PAYBUILDER_DESIGN.md          every screen, word, state, motion and measure (binding)
3. docs/design/pay-builder-poc.html                        clickable prototype: open it in a browser, click all
                                                           four homes and both example pay schemes. It defines
                                                           look, tone and behaviour. Its right-hand column is
                                                           simplified: the real one stays as it is today.
4. docs/handovers/paybuilder/PAYBUILDER_FACTS.md           verified code facts with file:line. Do not re-derive
5. docs/handovers/paybuilder/PAYBUILDER_BUILD_HANDOVER.md  scope, non-goals, architecture, payload shapes,
                                                           phases P1-P5, 62 numbered tests, walks, release, report
Then skim docs/handovers/newhire/NEWHIRE_LEDGER.md, docs/handovers/joining/JOINING_LEDGER.md and CLAUDE.md.

WHAT YOU ARE BUILDING (one paragraph)
Step 3 of Add employee today asks for a monthly wage and shows "The scheme's usual answers". It cannot show
what the wage becomes, and on a pay scheme that starts from another amount (live case: a yearly package) the
new person is paid nothing. Replace both cards with one block, the Pay Builder: HR types what was agreed and
the person's pay scheme works the whole month out as they type: earnings, deductions, what the company pays
on top, take-home. Lines the scheme marks as per-person are inputs and are saved on the contract. Lines with
a formula are locked, and each opens to show its sum in plain words with this person's numbers. Lines that
arrive each month are shown at their usual amount with an optional what-if. A link works back from a wanted
take-home to the pay. The same block is then used on the Hiring offer, in the contract panel as a dated
"Change pay" with before and after, and read-only on the new person's joining page. Formula Studio's
"Contract component" tick box becomes a plain two-way choice with a head-count warning.

HARD RULES (full list in the ledger and handover)
- New module pb_pay_builder holds the shared block and its server facade. Extend pb_new_hire, pb_formula_studio,
  pb_pay_package, pb_contracts (JS/XML only), pb_job_change and pb_joining by inheritance or small seams; list
  every edit to an existing module in your report.
- One engine. Work the month out with the existing compiled record-free engine and reuse the existing
  take-home search. No second evaluator, no pay arithmetic in JavaScript, no external LLM, no formula text sent
  to the browser.
- Do not change how a pay run reads its inputs, the automatic fill, or the pay-band totals. Do not restyle the
  right-hand column of Add employee. Do not change any scheme's data at release.
- The word "Odoo" must never appear in anything a user can see (screens, emails, public pages, manifest name
  and summary, translations). Technical identifiers are untouched.
- Match the existing design system exactly: indigo #5A4BB0, the studio's --pbnh-*/--pbim-* tokens, Manrope +
  Inter, Lucide icons through the icon helper, the measures in DESIGN section 12. No emoji, no gradients, one
  solid primary button per surface. Quality bar from the owner: "extreme WOW, intuitive, out-of-this-world
  experience, best in class". Compare your screen side by side with the prototype before calling it done.
- Do not widen who can see pay. Each of the four homes has its own gate (handover 3.8); unit-test every row.
- English, Vietnamese (vi_VN) and Indonesian (id_ID) from the start.
- No new server packages or standard-module dependencies. Never touch the abm database. No credentials, client
  names or real personal data in the repo; demo records are prefixed DEMO.

HOW TO WORK
- Phases P1 -> P5 in order (handover section 5). At the end of each phase: run that phase's numbered tests plus
  the full suites of every module you touched (baseline failures only), do that phase's browser walks with the
  console open, commit ("PAYBUILDER P1: ...") with explicit file staging, push.
- Record a test baseline for pb_new_hire, pb_formula_studio, pb_pay_package, pb_contracts, pb_job_change,
  pb_joining and pb_hiring BEFORE changing anything.
- A screen is not finished until you have used it in a real browser, in all its states, at the listed widths,
  in three languages, with the keyboard only and with reduced motion. Save screenshots under
  docs/handovers/paybuilder/shots/.
- Where the facts file says NOT VERIFIED, find the answer (a test is the best proof) and write it in the report.
- Append every new gotcha to PAYBUILDER_LEDGER.md section 4.

RELEASE (the owner decided you also release)
Follow handover section 9 exactly: read /opt/deploy-notes.md on the server first, use tools/release.sh (tier
risky, +pb_pay_builder to install) for all five databases (payobook, payobook_template, p0clone, rize, sudima),
verify, run the "no scheme changed" check, write the NOTE line, then do the live proof on payobook only with a
DEMO-prefixed person. On rize, look at step 3 for an India hire and leave without sending. Create nothing on
rize or sudima. If the release script does not return OK, stop and report; do not improvise. If you need a
live sign-in, ask me to sign in for you; never store a password.

WHEN YOU FINISH
Write docs/handovers/paybuilder/PAYBUILDER_REPORT.md in the format of handover section 10 (what was built,
test counts before/after, every deviation from the design and why, resolved unknowns, walk results with
screenshot paths, the honest self-score against the quality bar, release result, new ledger entries, open
questions for the owner in plain non-technical English). Then give me a short plain-English summary: what now
works, what I should click to see it, and anything you need me to decide.
```
