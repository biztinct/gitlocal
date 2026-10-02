# RIZE P8 — pb_rnr: recognition that pays

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + phase-log P0–P7 (code wins). Design doc:
`docs/design/rize-hrms-blueprint.html` §10 + §17 (wow: recognition wall + anniversary
engine — BOTH in scope).

## Scope
ONE new module `pb_rnr` (depends: pb_comp_ben (feed service), pb_me_portal, pb_lifecycle):
1. Company values + nominations (portal submit, HR alert, manager feedback/approval).
2. Recognition register + quarterly cycles (top-performer selection).
3. Monthly mood-board digest email; cash awards → payroll via P7's feed.
4. **Recognition lens** on the People hub.
5. **WOW — Recognition wall**: a live wall of approved shout-outs on the Home mission.
6. **WOW — Anniversary engine**: birthdays + work anniversaries surfaced to managers +
   the monthly digest.
7. Portal `/my/recognition`: nominate + my history.

### Binding NON-goals
- No gamification/points/badges economy — human nominations only. No Slack. No changes to
  P7 beyond calling its public feed API.

## Verified plumbing facts (do NOT re-derive)
- P7 feed: `pb.oneoff.feed.queue...` (exact signature in P7 report) with source='rnr';
  incentive records carry source rnr — cash awards CREATE a pb.incentive (kind spot,
  source rnr) and ride its approval+letter+feed lifecycle; do not duplicate that machinery.
- Digest mail canon: publish_notify pattern (gate, cap, honest counts). mail.template canon
  pb_pay_delivery.
- People-hub lens registry: as P2 used (see its report). Palette 2800s.
- Home mission: `pb_home_hub` — find how its lenses/cards compose (`static/src/js/home_hub.js`)
  and add the wall as a lens via ONE minimal additive mechanism (soft registry if present,
  else a documented small edit; the ledger P0 report may have added a generic pattern).
- Birthdays: `hr.employee.birthday` (private field — check exact name/perm on this build);
  anniversaries from join date (`first_contract_date` fallback chain,
  `pb_people/models/pb_people.py:22-30`).
- Employee photos: `image_128` on hr.employee for wall/board avatars.
- Portal canon pb_me_portal; own-record rules.

## Architecture

### Models
**`pb.company.value`** — name, motto Char, description, icon Char (ic key), color Char
(token name, not hex), sequence, active, company_id. Seed 5 generic-but-real values
(Ownership, Care, Candour, Excellence, One team) — owner can edit.

**`pb.rnr.nomination`** — mail.thread + biz.approval.chain.mixin (manager step → HR step).
nominee_id (hr.employee), nominator_id (hr.employee, from session for portal), value_id,
story Text required (the real example), submitted_at, state (mixin) + outcome Selection
`[('recognised','Recognised'),('awarded','Cash awarded'),('declined','Not this time')]`,
award_amount Monetary optional, incentive_id (P7, when awarded), quarter_id optional,
public Boolean default True (nominator can untick; wall shows only public+recognised),
company_id. On HR approval → outcome recognised (+ optional award → create pb.incentive
source='rnr' and link); nominee congratulation mail (gated); HR alert on submit.
Constraint: nominee ≠ nominator.

**`pb.rnr.cycle`** — name ("Q3 2026"), date_from/to, state open/selecting/closed,
top_ids m2m nominations (the chosen winners), notes, company_id. "Roll up" action:
per-nominee counts by value for the window; selecting winners marks their nominations
awarded (with amounts → incentives via the same path).

**Mood-board digest** — monthly cron (idempotent by month stamp in ir.config_parameter):
build a designed HTML email (inline CSS, brand palette): this month's recognised stories
(photo, value chip, story excerpt), new joiners welcomed, birthdays + work anniversaries
NEXT month (anniversary engine), quarterly winners when fresh. Send to all-active-employee
work emails via publish_notify-style loop (gate `pb_rnr.digest_mail` default '0', cap,
honest counts). Also render the same content at a backend preview action.

**Anniversary engine** — daily cron: employees with birthday today / work anniversary
today (years>=1) → congratulation mail to the person (gated `pb_rnr.anniv_mail`) + a
heads-up mail to their manager listing this week's upcoming ones (weekly batch, Monday,
idempotent). Data method `upcoming_celebrations(days)` reused by digest + wall.

### Recognition lens (People hub, palette 2800s)
Facade `pb.rnr`: board of nominations {nominee (photo), value chip, nominator, story
preview, state, outcome, amount}; kpis (this month, awaiting manager, awaiting HR,
awarded QTD); facets (value, state, quarter); dialogs: nominate (same as portal),
review/approve (shows the story big, value, history of nominee), cycle roll-up view
(ranked table, pick winners, set amounts → plain-English confirm listing the money
consequence). Screenshot-worthy.

### WOW — Recognition wall (Home mission)
A lens/card on the Home hub: masonry-ish wall of recent public recognised nominations —
big value chip, story, nominee photo + name, nominator credit, subtle entrance animation
(CSS only, respects prefers-reduced-motion); side rail: this month's celebration strip
(birthdays/anniversaries, no dates-of-birth shown — name + day only); quarterly winners
banner when a cycle just closed. Read-only, cached facade (cap 30 stories), every
employee-visible (internal users); portal users get the same content on /my/recognition.

### Portal `/my/recognition`
Nominate form (value picker with mottos, story textarea, nominee search limited to
same-company active employees, public toggle) → thanks state; my nominations (sent +
received) with outcome chips; the wall content below (same data, portal-rendered).
`/my` counter: none. Controller-boundary writes (sudo scoped), own-read rules.

## Safety rails
- All outbound mail gated OFF during tests; @example.com actors; digest tested to a
  single test address override (`pb_rnr.digest_test_email`) before enabling broad send —
  leave broad send OFF and tell the owner how to enable (final report).
- Cash award path creates incentives but does NOT queue them into a run automatically —
  queueing stays the explicit P7 lens action (money never moves without a human pressing
  the money button).
- Nominee privacy: declined nominations never appear anywhere public; stories are visible
  to HR + the nominator + (once recognised & public) everyone.
- Deploy `-i pb_rnr` (+ minimal `-u pb_home_hub` if the wall needed an edit — document).

## Numbered test cases
T1. Deploy clean.
T2. Portal nominate (test user → demo colleague, value + story) → HR alert queued;
    manager sees it in their approval (chain step), comments/approves; HR approves →
    recognised; nominee congrats mail queued (gate on).
T3. Nominate self → friendly refusal. Nominee search excludes other companies.
T4. Award path: HR approval with amount 100 → pb.incentive (source rnr, spot) created
    linked; it rides P7 approval; queue via P7 lens preview shows it (do not run a full
    pay run — P7 already proved that; just show queued state works) → nomination outcome
    awarded.
T5. Recognition lens: board + facets + review dialog render; roll-up for the current
    quarter ranks nominees; pick a winner with amount → incentive created; plain-English
    confirm shown; light+dark screenshots.
T6. Wall on Home: public recognised stories render with photos + animation; a declined
    and a non-public one do NOT appear; celebration strip shows upcoming
    birthday/anniversary of test data; reduced-motion honoured (emulate).
T7. `/my/recognition`: wall + my sent/received with outcomes.
T8. Digest: force-run for this month to the TEST address only → single designed email,
    stories + celebrations correct; rerun same month → idempotent skip.
T9. Anniversary crons: employee with today anniversary (fixture) → one congrats (gate
    on, test address); manager Monday batch lists the week; rerun → no dupes.
T10. White-label grep zero; plain English; no emoji (Lucide only) including in EMAILS.
T11. Regressions: People hub other lenses fine; Home hub loads for a plain user;
    P7 incentives lens unaffected.
T12. Clean up fixtures; report gate states (digest broad send left OFF + how to enable).

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, gotchas, wall integration mechanism
on Home, digest enable instructions for the owner report, palette ids.
