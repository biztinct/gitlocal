# PSCHEME P3 — merge, lessons, release ×5, fill DRY RUN on every site

Read first: `PSCHEME_LEDGER.md` (all of it, incl. PS, PS-a, PS-b gotchas on all three branches), the three phase
reports (`PSCHEME_P1_REPORT.md`, `PSCHEME_P2A_REPORT.md` on branch `pscheme-p2a`, `PSCHEME_P2B_REPORT.md` on branch
`pscheme-p2b`), `PSCHEME_FACTS.md` §10.2 and §11, and for the release: repo `CLAUDE.md` (deploy contract),
`docs/handovers/newhire/NEWHIRE_P8_REPORT.md` §6 + the scripts under `docs/handovers/newhire/p8/` (`nh8_prep.sh`,
`nh8_tries.sh` — the risky-tier ritual to clone), `NEWHIRE_LEDGER.md` release gotchas (NH76: never as the owner's
admin; cron snapshot trap; hidden-copy rehearsal; copies run live jobs — switch jobs and mail servers off first,
`dropdb --force`), and `/opt/deploy-notes.md` on the server.

Worktree `gitlocal-worktrees/pscheme`, branch `pscheme`.

Rails (ledger §0): design mandate verbatim **"extreme WOW, intuitive, out-of-this-world experience, best in class"**;
Lucide, no emoji; plain screen words; **never "Odoo" in a user-visible string**; vi_VN + id_ID for every new string;
public repo — no client names / data / credentials in any commit, report or script (client figures go only to
`outputs/` in the main checkout, never committed); backend needs a screen twin; no effort on past pay runs.

Architect confirmations of the P2 deviations (binding): P2a 1 (a waiting many-person request is refused whole when
anyone in it moved — keep), 2 (the fill never changes a contract — keep), 3–10 accepted. P2b 1–5 accepted, except
P2b-3 which you fix in A.3.

## A. Merge and tidy (local)
A.1 Merge `pscheme-p2a` then `pscheme-p2b` into `pscheme` (both-sides additions: keep both; `pb_scheme_map` manifest
    = higher version then bump once more; same for `pb_hr_payroll_formula`). Then merge `origin/19.1` (other
    sessions shipped since) and resolve.
A.2 Run the three phases' new tests together + the P1 suite list (same-before/after against `origin/19.1`): nothing
    may fail only after. Re-walk in the browser the two places where the streams meet: (i) Change job to another
    country → the person's Pay scheme block, the amber line and the contract currency note agree; (ii) a joiner
    added from the upload sheet → appears under "have their own" on the Mapping board and is "Already have their
    own" in the fill drawer. Console clean.
A.3 Sheet rows get their own source (`sheet`, shown as "Upload sheet") instead of `import` ("Pay data file").
A.4 Translations: the ~25 `pb_scheme_map` strings with no entry (PS-a8) get vi_VN + id_ID; fill the old `id_ID.po`
    gap for `pb_scheme_map` (149 older strings) so the Mapping board is whole in Indonesian. Parse gate.

## B. Lessons follow the screens (`pb_learn`; owner ruling R10)
B.1 Rewrite every sentence that says the team decides the pay scheme (inventory: FACTS §10.2; P1 report §8; P2a /
    P2b reports): `learn_content.json` (en + inline vi; ~lines 3462, 5841, 15337, 15353, 25294, 34401),
    `anchors.json` (~2223, 2304), and the new-employee replica `static/src/engine/screens.js` (~400–412: the replica
    must run Country of work → Pay scheme, like the live screen). Truth to teach: each person has their own pay
    scheme, pre-filled from their Country of work; a team's scheme is only the usual starting point; a change starts
    with the next pay run; Mapping's "Give everyone their pay scheme".
B.2 If the lesson generator wipes `pb_learn` `vi_VN.po`, restore it (known trap). Open the changed lessons and the
    replica in the browser (en + vi), console clean. Bump `pb_learn`.

## C. Release ×5 (risky tier: this changes who is in a pay run)
C.1 Commit, then push `pscheme` to `19.1` (fast-forward or merge; scan for passwords; feature-scoped history kept).
C.2 Databases: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`. **Never abm.** Clone the P8 ritual:
    read the deploy notes (respect any HOLD or open START — if another session's release is open, wait, do not
    race); prep (staged tree = the commit; dependencies; vi + id active; dumps ×5 read back; job snapshot as COUNTS
    per database); rehearsal on hidden copies of `rize` and `payobook` (jobs + mail off on the copy first): upgrade
    exit 0, 0 ERROR, versions, then **the fill dry run on the copy, and on the rize copy also the REAL fill followed
    by building a pay-run population for each scheme for next month (everyone in exactly one main run; nobody
    missing who was paid before) and the on-screen Undo path** — then drop the copies.
C.3 Go-live: START line; quiet check on rize / payobook / sudima; lock; go-live dumps; stop; per-module scoped
    rsync (`--delete` scoped to ONE module, never the addons root; ONE addons directory); `-u` the changed installed
    modules one database at a time; asset purge + assets version per database; start; DONE line. A new module is
    installed nowhere unless a changed module depends on it (report). Roll back from the dumps on any ERROR.
C.4 Verify: trees byte-identical (skip `__pycache__`, `*.pyc`, `.DS_Store`); manifest = installed version ×5
    (normalise the `19.0.` prefix); job counts identical except the ONE new daily job
    (`pb_scheme_map.cron_person_scheme_boundaries`) — and no job re-activated on payobook (demo mail spam lock);
    0 ERROR / Traceback since the stop; five sites answer 200; a read-only check per database that
    `pb.person.scheme` exists with 0 rows and that every active person's "who pays them" answer is the same as before
    the stop (the engine with no rows must change nothing).
C.5 Live browser look, read-only, with the QA login on payobook only (never the owner's admin): the Pay scheme
    block on one person, the Mapping board banner, the Change pay scheme dialog opened and closed without saving.

## D. Fill — DRY RUN ONLY on live (the owner sees the counts before anything is written)
D.1 Per database, per company, read-only (`fill_apply(..., dry=True)` — confirm in code it writes nothing, and wrap
    in a rolled-back transaction anyway): people; Ready; From Country of work; Check these; Needs your choice
    (several / no scheme for the country / no Country of work); Already have their own; schemes named only as
    "scheme 1 … n (country, kind)". Also: how many people have no Country of work, and how many of those "Fill empty
    Country of Work" would fill.
D.2 **Do NOT run "Fill empty Country of Work" and do NOT apply the fill on any live database.** The architect asks
    the owner with your table. Leave a ready, tested apply script on the server next to the dumps (clone of
    `p8/nh8_map.py`: `MODE=dry|apply`, per database, writes `person_scheme_fill_<db>.csv` of created row ids as the
    undo record, START/DONE lines) and state the exact command.
D.3 The client-readable table with real team / scheme names goes ONLY to
    `/Users/adity/Documents/GitHub/gitlocal/outputs/pscheme-fill-dry-run-2026-11-27/` (never committed).

## Binding non-goals
Applying the fill live. Any data change on a client database. Two-country split. New features.

## Report back — `PSCHEME_P3_REPORT.md`, committed + pushed on 19.1
Result line · merge notes · tests + suites · lessons changed (list) · release timeline (UTC), downtime, per-database
exit / time / ERROR / jobs before → after · verification table · the dry-run table per database (counts only, no
names) · the exact apply command and the undo path · what is left on the server and locally (worktrees `pscheme`,
`pscheme-p2a`, `pscheme-p2b`, local databases `ps_*`, `ps2a_*`, `ps2b_*` — drop the ones you can) · gotchas to the
ledger · owner questions in plain non-technical words. Usage limit: commit WIP + PAUSED; **never pause between the
service stop and the service start** — check the limit before the stop.
Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
