# NAV P3d — Home: Ask HR as a Payobook board

Read first: `docs/handovers/NAV_LEDGER.md` (P2 live-walk row on the stock empty state); `docs/handovers/NAV_P2A_REPORT.md`
(A7: Home › ASK HR today = the standard kanban embedded through the web `View` component, `pb_ask_hr/static/src/js/askhr_lens.js`).
Owner decision 2026-10-21: redesign it as a Payobook quiet board, after P3c. Design mandate: legacy surfaces touched get
the WOW treatment; native views may remain only off-menu as admin fallbacks. Implementer: Opus.

## 1. Goal

Home › ASK HR becomes a Payobook board like Praise or Exits: a glance line, four quiet steps, cards with the person,
category, age and owner, filters that are words not menus, a proper empty state, keyboard and bulk ergonomics, and the
same record rules (HR sees all, an employee sees only their own). The native kanban/list/form stay as the off-menu
admin fallback and as the form that opens from a card.

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| Model `pb.ask.hr.ticket`: states `new, with_hr, answered, closed` (`pb_ask_hr/models/ticket.py:57-60`), `group_expand` (`:91`), owner field (HR owner), category, `answered_on`; filters "Mine", "Nobody has it yet", per-state filters; group by owner/category (`ticket_views.xml:124-137`); action `pb_ask_hr.action_pb_ask_hr_ticket` (`:144-154`) opens with `search_default_filter_open`; employee rule `rule_pb_ask_hr_ticket_own` (`security/pb_ask_hr_security.xml:17-21`); portal page `/my/ask-hr` (`controllers/portal.py:145-291`). | agent fact-find 2026-10-20 |
| P2 lens: `askhr_lens.js:67-75` registers key `askhr`, seq 15, groups `base.group_user`, Component `PbAskHrLens` rendering `View` kanban; Home sidebar item claims the action and model. | NAV_P2A_REPORT.md A7 |
| Board pattern to clone: Praise (`pb_rnr/static/src/js/rnr_board.js`, steps `:151-154`, strip `:189-193`, xml `rnr_board.xml`) or Exits (`pb_offboarding/static/src/js/exits_board.js:193-223`); QuietGlance/QuietSteps `t-call` templates (`pb_import_kit/static/src/xml/quiet_board.xml:26,38`); `ic` icons from `@pb_import_kit/js/import_icons`; `.pbim` tokens. | |
| Hub lens props: `{embedded:true, ...def.props}`; `wantsArrival` gives `arrival{lens, focus}` (`hub_shell.js:359-375`). | |

## 3. Design (R11 bar; plain words; Lucide; no "Odoo")

- **Glance line (hero):** "**5 new** · **3 with HR** · **2 waiting on the person** · **8 answered this week** · median first reply 1.4 days" — each a filter (QuietGlance; tones: new amber when >0 older than 2 working days, otherwise grey).
- **Steps:** New · With HR · Answered · Closed (QuietSteps; counts; "mine" flag on With HR when the owner is me). Cards in the selected step, newest first; a card: reference, person (avatar, name, department), category chip, one-line question, age ("2 days"), owner chip or "Nobody has it yet" (amber), unread reply dot. Keyboard: arrows move, Enter opens.
- **Filters (chips):** Mine · Nobody has it yet · category chips (from the category field values in the data) · search (reference, name, text). Persist in `pbhub.askhr.filters.v1`.
- **Actions:** card click → the existing form in a side sheet (`target:"new"` form) with Home as the way back; **Take it** (assign to me) and **Hand to…** (owner picker) on a card for HR; bulk: select several → Take it / Hand to… / Close with a note. All through a facade `pb.ask.hr.act(verb, payload)` that calls the existing model methods (do not reimplement state changes; if a method is missing, add one on the model and reuse it from the form).
- **Employee view:** the same board but only their own tickets (rules apply; read as the user, never sudo), no owner actions, "Ask a new question" button that opens the portal page `/my/ask-hr` in the same tab.
- **Empty states:** HR, nothing open → "Nothing is waiting. Last question answered 2 hours ago." + "Show closed"; employee, nothing → "You have not asked HR anything yet." + the Ask button; filtered → "Nobody matches" + Clear.
- **Motion:** step change slides the card list 120 ms; nothing else.

## 4. Non-goals
No SLA engine (a median first-reply number is computed from `answered_on - create_date` for the last 30 days and labelled as such; no targets, no pauses); no portal change beyond linking; no category admin; no email changes.

## 5. Tests
Python `pb_ask_hr/tests/test_board_p3d.py`: glance counts; steps counts; an employee sees only own tickets through the facade (no sudo leak); Take it / Hand to / Close via the facade move state and owner exactly as the form does; median computed over the window; filters. Chrome: HR officer walk (take, hand, close with note, filters persist); employee walk (own only, Ask button); keyboard; empty states; Vietnamese; console clean.

## 6. Learn and Access
Anchors `ah-glance`, `ah-steps`, `ah-card` (repeats), `ah-take` reserved; practice replica: add a small `askhr` replica in `screens.js` (steps + three cards) since this is now a Payobook screen and lessons may point at it; station "home" outline sentence; regenerate; .po unchanged; bump pb_learn. Access: none.

## 7. Deploy (after Fable's go) — NORMAL tier
`-u pb_ask_hr,pb_learn`; p0clone first; PO gate; asset signal + purge + bump; bundle warm-up; cron snapshot; push after. Report `docs/handovers/NAV_P3D_REPORT.md`; stop at the deploy gate first.
