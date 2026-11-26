# PSCHEME P4 — rize fill re-run, "Usual pay scheme by country" on Mapping, the empty card

Owner card, 27 Nov 2026 (binding): (1) the rize staff refresh of 22:10 UTC 26 Nov was PLANNED — run the fill again on
rize for the new people; (2) the by-country fallback rules must be visible AND editable on the Mapping screen;
(3) re-word the "Nothing is attached to a scheme yet" card, shipped with the same release.

Read: `PSCHEME_LEDGER.md` (rules, R1–R9, A1–A15, gotchas), `PSCHEME_CLOSEOUT.md` §6 (F1: the shape of rize's rules,
the screen-twin gap), `PSCHEME_FACTS.md` §1.1 (rule lines: a `hr.formula.scheme.assignment` with a `domain` and
neither team nor division; first rule in sequence wins; **a rule ignores the kind of run**, T5) and §5 (approval kinds).
Rails: design mandate verbatim **"extreme WOW, intuitive, out-of-this-world experience, best in class"**; Lucide, no
emoji; plain screen words; **never "Odoo" in a user-visible string**; vi_VN + id_ID for every new string; no client
names / figures in committed files; dependency rail; lessons follow screen changes.

## A. rize — fill again (now, before the build; no service stop)
`ps3_fill.sh rize apply` (dump first, START/DONE, undo list): only people without a row are offered; the 215 who have
one are untouched. Verify as before (answers with the person rule identical before/after for everyone; next month's
populations: nobody twice, nobody missing; "Work it out again"; banner count). Report counts and who is left and why
(counts only). Archived people keep their rows (history) — confirm they are in no population.

## B. Mapping › Who is paid by what › "Usual pay scheme by country"
Truth to show: the safety net for someone who arrives WITHOUT a pay scheme of their own is, in order, their team's
usual scheme (optional), then their country's usual scheme. Today the second one is invisible.
B.1 Definition: a **country line** = an active rule line of exactly the shape `[('payroll_country', '=', <value>)]`
    (company-scoped as F1 wrote it), one per (company, country). Everything else with a domain is an "other rule".
B.2 Section on the board (below the header banner, above the teams; collapsible, remembers its state; quiet when all
    is well): one row per Country of work that has active people or an active scheme in this company — flag-less,
    Lucide globe; "Vietnam · 70 people · 0 rely on this today" (people of that country with no row of their own and
    no team / division line) ; the scheme as a chip with a chooser (active schemes of that country, never a mid-month
    advance; several → radio cards as in the Change pay scheme dialog); states: set · **not set** (calm amber only
    when someone relies on nothing: "2 people here have no pay scheme and nothing catches them" + "Choose") · country
    with no active scheme (the reason + the existing link). Actions: Choose / Change / Remove, keyboard reachable,
    one live sentence of consequence before saving ("New people in Vietnam without a pay scheme of their own will be
    paid by <scheme>. Nobody with their own pay scheme changes."). Hero moment: **the invisible safety net becomes
    four plain lines — and the one hole in it is the only thing in colour.**
B.3 "Other rules" (anything with a domain that is not a country line): read-only list under a disclosure, each in
    plain words ("A list of 70 named people → <scheme>", "People matching a special rule → <scheme>" + how many it
    reaches today), with "Set up by support" — no edit; Remove only if it reaches nobody a country line or own row
    does not already cover, through the same approval (otherwise explain why not).
B.4 Server: new kind `country_set` on `pb.schememap.proposal` (set / change / remove one country line; same route,
    fast lane, re-check, audit; proposer rights as `person_set`, carry-out gate unchanged). Setting never touches
    team lines, person rows or other rules; sequence = after existing other rules of that company (so a narrower
    named-people rule still wins), report if that ordering ever changes somebody's answer. Stale marks as map lines
    already do. Refusals in plain words (scheme not active / other company / other country without an explicit
    "this scheme is of another country" confirmation / mid-month advance).
B.5 Coverage reasons and the "not covered" list name the fix: "Choose a usual pay scheme for <country>" beside the
    two existing fixes. Add employee's "No pay scheme for <country> yet" is unchanged.
B.6 One lesson sentence (`pb_learn`, en + vi) on the Mapping "Who is paid by what" lesson: the country line as the
    safety net. Bump `pb_learn`.

## C. The empty card
`scheme_map.xml` "Nothing is attached to a scheme yet — You have been paying people for months, so the map already
exists…" → when everyone (or almost everyone) has their own pay scheme: title "Everyone is paid by their own pay
scheme", body "Giving a team a usual pay scheme is optional. It pre-fills new people in that team." + the existing
suggest action as a secondary button; when people still follow nothing: keep a call to action but point at "Give
everyone their own pay scheme". Dead msgids removed.

## Tests (coverage binding)
T1 country line detection (exact shape only; company scoping) · T2 board payload rows: people, "rely on this" counts,
set / not set / no scheme · T3 `country_set` set / change / remove, fast lane and second approver, re-check, audit ·
T4 a person with no row and no team line is answered by the country line; with an own row unaffected; a named-people
rule earlier in sequence still wins · T5 rights (HR officer proposes, cannot carry out; portal refused) · T6 other
rules listed read-only with the right counts; Remove refused / allowed per B.3 · T7 refusals · T8 empty card states ·
T9 static: no "Odoo" / rung / config / cycle; vi + id complete (parse gate) · T10 the 99 pay-scheme tests + the
dependency rail still pass. Suites before / after for `/pb_scheme_map,/pb_hr_payroll_formula,/pb_formula_studio,
/pb_new_hire,/pb_learn`.
Walks (local, en + vi, console clean, 340 px for the chooser): set a missing country line (fast lane) → the amber
hole goes grey; change; remove; second-approver lane; other rules disclosure; empty card both states; a new person
added with that country and no scheme → answered by the line.

## Release ×5 — normal tier plus a dump of each database (a new approval kind; no stored-data change)
Deploy notes (HOLD / open START respected), START, quiet check, dumps ×5, stop, per-module scoped rsync, `-u` changed
modules one database at a time (stop at first failure), asset purge + version bump, start, DONE; hash + version +
log + job counts before/after (nothing re-activated; payobook's demo-mail job stays off); five sites 200. Then on
rize, read-only: the section shows the four country lines F1 / earlier work created, the named-people rules under
"Other rules", zero holes. Check usage headroom before the stop; never pause between stop and start.

## Report back
Append §7 to `PSCHEME_CLOSEOUT.md` (A counts; B/C what changed on screen; tests; walks; release table + downtime;
anything unexpected; open items), commit + push 19.1. Final message: the same, short, with owner questions in plain
non-technical words. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
