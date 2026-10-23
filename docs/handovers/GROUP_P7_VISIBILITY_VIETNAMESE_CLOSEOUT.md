# GROUP Phase 7 — "Visibility, Vietnamese, closeout": who sees what, every word translated, the seven polish items, and the closeout

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules, rulings, gotchas GR1–GR53,
the phase log for P1–P6b), then Part A "Reading the numbers" (division-head visibility)
and Part H of `docs/design/group-blueprint.html`, then `docs/handovers/WFPLAN_CLOSEOUT.md`
and `RIZE_CLOSEOUT.md` as closeout precedents. GR24/WF15: temporary validators.

## 0. What you are building, in one paragraph

The programme is functionally complete. This phase makes it finished. **Visibility**:
a division head sees only their division, country HR sees their country, a group CFO or
the CEO sees everything, on every GROUP surface (Group screen, scheme map, Explorer,
Insights, Decision Room, Assignments, Pay). **Vietnamese**: every word on every GROUP
surface, including `pb_group`'s remaining terms, with a test that counts survivors.
**The seven polish items** each phase named as its "improve first", done. **Closeout**: a
document for the owner that says what is live and where, how to use it in ten minutes,
what the numbers are built from, the decisions still theirs, every temporary login and
debt, and what a Phase 8 could be; plus the ledger's final phase log.

## 1. Deliverables
1. `pb_group` 19.0.2.0.0: `pb.group.visibility` (per user: `kind` all|country|company|
   division, `ref`), a "Who sees what" card on the Group screen (assign per user, with a
   preview "As Nguyen, you would see: Retail · 902 people"), and the shared helper
   `pb.group.visibility.scope_for(user)` → allowed company ids + division ids + a
   sentence; record rules on `pb.division.link`, `pb.pay.review.line`, `pb.work.segment`,
   `pb.decision.plan` (by scope), and a domain clause every GROUP facade applies
   (`_visible_companies()`/`_visible_divisions()`); Explorer/Insights/Decision Room/
   scheme map/Assignments/Pay read it. A user with no row = the company switcher as
   today (nothing changes for anyone until a row exists).
2. Vietnamese sweep: `pb_group` (225 terms), `pb_scheme_map`, `pb_explorer` (new strings
   from P3), `pb_workseg`, `pb_pay` — 100% non-platform terms; the WFPLAN-style
   completeness test in each module.
3. The seven polish items (each with a before/after screenshot):
   - P1: bulk attach in the Group screen's department picker (tick many → "Attach these").
   - P2: wires as gestures on the "Who is paid by what" board (drag a team onto a scheme;
     hover a wire to trace it; pull a wire off to detach) with keyboard equivalents.
   - P3: a "look inside" cue on Explorer bars (hover affordance + an animated descent).
   - P4: the Decision Room dock as cards below 1200 px and a pinned actions column above.
   - P5: a live cheap estimate under the Assignments month strip while dragging (basic pay
     × share per entity, in each currency), with the exact preview behind it.
   - P6a: per-family money axis on Pay Bands ("Fit to this family"), plus a dense mode.
   - P6b: the review worksheet's "what to know" chips move under the person's name; the
     table no longer needs sideways scrolling at 1440.
4. Owner-debt cleanup that is safe to do: nothing destructive. List the rest.
5. `docs/handovers/GROUP_CLOSEOUT.md` (§4) and the final ledger phase log.
6. Deployed p9clone → payobook → abm → payobook_template; Chrome walks; commits; report.

Non-goals: no new features beyond the list; no dark palette for the kit (GR38 — say so in
the closeout as a platform item); no password resets; no push.

## 2. Design (the bar)
**"extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero of this
phase: the **"as this person" preview** on the Who-sees-what card — pick a user and the
card shows, in one sentence and a mini tree, exactly what they would see across the
product. Second: the P2 wires becoming a gesture. Plain English: "Who sees what",
"Everything", "One country", "One company", "One division", "As <name>, you would
see…". Zero dead-ends: a user with visibility but no matching data sees the sentence and
a link to ask an administrator; a scope that no longer exists (division archived) falls
back to "Everything they could see before" and warns the admin.

## 3. Tests (p9clone; numbered)
- T1 `scope_for` per kind; no row = switcher; archived scope fallback + warning.
- T2 record rules: a division-head validator on p9clone sees only Retail's rows in
  reviews, segments, plans, division links; the Explorer/Insights/Decision Room/Assignments/
  Pay facades filter to Retail (assert on people counts); an "everything" user unchanged.
- T3 "as this person" preview equals what that user actually gets (log in as them).
- T4 Vietnamese: 0 survivors per module (non-platform terms); `.po` compiles; GR5 comments.
- T5 each polish item has a test where testable (bulk attach writes N links in one call;
  wire drop calls the same create as the panel; estimate = basic × share; axis fit
  changes the scale; worksheet has no horizontal overflow at 1440 in a DOM assertion).
- T6 earlier suites green (same p9clone drift set); no `wfp` reference anywhere.
Browser (p9clone/payobook/abm; validators for CEO, country HR, division head, employee;
1440 + 390; Vietnamese; `docs/handovers/group_p7_shots/`): B1 Who-sees-what card + preview;
B2 division head walks every surface and sees only Retail; B3 country HR on payobook sees
Vietnam only; B4–B10 the seven polish items before/after; B11 Vietnamese user on every
GROUP surface with 0 English; B12 abm unchanged for its single company.

## 4. The closeout (`docs/handovers/GROUP_CLOSEOUT.md`)
Owner-first plain English, then engineering. Sections: 1) What is live and where (one
paragraph per surface: Group, Who is paid by what, pay run, Explorer breadcrumb/compare/
currency, Decision Room scope/rules/actuals/approvals/exact cost, Assignments + patterns,
Pay Bands/Fairness/Review/Changes/portal, Who sees what), with screenshots. 2) Ten minutes
to try it (numbered). 3) What the numbers are built from (scheme map, facts, rates, rule
sets, segments; what is an assumption). 4) Decisions still yours (reset the admin
password; enter exchange rates; confirm the seven non-VN rule sets with an adviser; turn on
joiner/leaver proration per company; switch the split-pay pattern; enter bands or accept
the proposal; assign visibility; push the commits — count them; kit dark palette as a
platform item). 5) Temporary logins created across P1–P7 and their state. 6) Engineering
summary: modules + versions per DB, commit range, test counts per phase, timings, the
gotcha range GR1–GR60ish, the invariants enforced, what was removed (the legacy module and
its tables), Phase 8 candidates (rate source connector; segment-aware statutory reporting;
review→pay-file lane automation; kit dark palette; full-bleed phone frame).

## 5. Report back
1. Three sentences: what a division head sees now, what a Vietnamese user sees, what
   changed in the seven places.
2. T1–T6 / B1–B12 table; Vietnamese counts per module.
3. Deploy evidence per DB; closeout path; final commit list and the total unpushed count.
4. Deviations; new gotchas; self-score.
