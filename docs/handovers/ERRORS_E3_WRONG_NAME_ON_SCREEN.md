# ERRORS · Phase E3 — The last two places a person sees the wrong name

**Read `docs/ERRORS_CONVENTIONS.md` first** (ER1–ER19, binding, not restated here), then
`ERRORS_E1_BREAKDOWN_SCREENS.md` and `ERRORS_E2_REMAINING_LEAKS.md` for what shipped.

E1 and E2 closed every place the **vendor's** name reached a screen through an error. E3
closes the two that are left, and the second one is the opposite problem: **our own**
product name reaching a tenant's screen.

Two items. They are independent. Do E3-1 first — it is small and it will teach you how
the field pipeline behaves before you touch the bigger one.

---

## E3-1 — The vendor's name in field tooltips, in Vietnamese

**The evidence, counted on the live databases 2026-09-11 (identical on all three):**

| | payobook | rize | abm |
|---|---|---|---|
| `ir_model_fields.help` rows matching the vendor word | 37 | 37 | 37 |
| `ir_model_fields.field_description` rows matching | 5 | 5 | 5 |

Observed on screen during E2: the Vietnamese Settings page rendered
`help="Cho phép người dùng đăng nhập/xuất từ Odoo."` (from `hr_attendance`).

**Step one is a diagnosis, not a fix. Three candidate seams, and the evidence cuts
against the obvious one:**

1. `web_debranding/models/ir_translation.py:88` overrides
   `ir.model.fields.get_field_help`, and core really does call it
   (`odoo/orm/fields.py:965`, and `get_field_string` at `:958`). Its `debrand()`
   (`ir_translation.py:31`) guards on `re.search(r"\bodoo\b", source, re.IGNORECASE)`,
   which the Vietnamese string **does** match. So on paper this should already work.
   Find out why it does not. Note both overrides are wrapped in
   `@tools.ormcache("self.env.context.get('lang')", "model_name")` — **a stale cache is
   a live suspect**, and `scrub.py`'s header states as fact that `ir_model_fields*` is
   "already debranded at runtime" by these methods. That claim is what this phase
   disproves; correct the comment when you know the truth.
2. The backend form arch path (`base.get_view` → web_debranding's `debrand`), which is
   **not** `biz_debrand`'s `_get_view_etrees` seam — that one only covers
   server-rendered QWeb (ER1). A `help=` written into a settings view's XML travels this
   way, not through `ir_model_fields` at all. Establish which of the two the observed
   string actually is before fixing either.
3. `biz_debrand`'s own `_()` patch, which cannot reach a jsonb column.

**Then fix it in `biz_debrand`, not in `web_debranding`** — that module is gutted on
Odoo 19 and is not where coverage goes (memory `debranding-architecture`). Prefer a
runtime seam over adding these tables to `scrub.py`: `-u` re-imports field help from
source on every upgrade, so a scrub is a fix with a half-life.

**Tests.** The exact `hr_attendance` string, rendered in `vi_VN`, contains the brand and
not the vendor. A field whose help is clean is returned untouched. The fix survives a
registry reload (whatever the cache turns out to do). The English rendering is still
correct. Count the matching rows before and after on `rztest`.

---

## E3-2 — Our own product name, shown to a tenant as if it were theirs

**The problem.** A Rize employee is greeted with "Welcome to Payobook". The product name
is typed into screens rather than read from the tenant's settings. Same fault as the
vendor name, pointing the other way, and it will hit every tenant we ever add.

**The evidence, counted 2026-09-11 across `pb_*` and `biz_*`, comments excluded:**

| Where | Occurrences |
|---|---|
| XML element text and prose attributes | 159 |
| JavaScript string literals | 52 |
| Python `_()` messages | 18 |
| **Total** | **229** |

**Do not edit 229 places.** The machine that solves this already exists and you extended
it twice in E2. `biz_debrand` has one canonical rewrite (`models/brand.py:70`
`debrand_text`) mirrored character-for-character in
`static/src/js/biz_debrand_runtime.js:76`, reaching screens through four seams: the
Python `_()` patch, the QWeb tree walker, the JS `_t()` patch plus template processor,
and E2's notification seam. Teach it one more rule.

**The design, and its three traps.**

*The rule.* A new parameter — suggested `biz_debrand.product_name`, default **empty** —
naming the master product name to replace. When set, it is rewritten to
`biz_debrand.brand_name`. On `payobook` and `abm` the brand already **is** `Payobook`, so
the rule is a no-op and those databases cannot regress. On `rize` (brand `Rize` since
2026-09-11) all 229 become correct at once. `payobook_template`, `p9clone` and `rztest`
still carry the `BizApp` placeholder; leave them.

*Trap 1 — the rule must NOT apply everywhere `debrand_text` is called.* `scrub.py` uses
the same function to rewrite **stored rows**. A company genuinely named "Payobook
Vietnam JSC", a partner, an employer on a payslip — those are data, and renaming them
would be a silent data corruption far worse than the bug. Make the product rule an
explicit opt-in argument on `debrand_text`, off by default, and pass it only from the
seams that render **source** text. Say in your report exactly which call sites you
turned it on for.

*Trap 2 — the existing guards were written for one word and must be re-derived for
another.* `WORD_RE` (`brand.py:40`) is tuned to `odoo` — it excludes the JS namespace,
`@odoo-module`, `/odoo/` paths. The product name appears in different shapes: module
prefixes, database names, `payobook.com` in URLs and in e-mail addresses like
`demo@payobook.com`, XML ids, model names. Work out the guard set from the actual
occurrences, not by analogy. `URL_ATTRS`/`debrand_url` and `OPAQUE_TAGS` already exist
and already do the right thing — reuse them rather than inventing a second set.

*Trap 3 — keep the two implementations identical.* `brand.py` and
`biz_debrand_runtime.js` are pinned together by `biz_debrand/tests/test_rewrite.py`.
Extend that test in the same commit.

**Tests.** With the parameter unset, nothing changes anywhere (prove it — this is the
rollback). With it set and brand `Rize`: "Welcome to Payobook" becomes "Welcome to Rize";
`payobook.com`, `demo@payobook.com`, `pb_import_kit` and a model name are untouched; a
stored company named "Payobook Vietnam JSC" is untouched through `scrub.py`; the Python
and JS rewrites agree character for character. On `payobook` the whole rule is a no-op.

---

## Deploy, verify, report

Deploy per `CLAUDE.md` and install/upgrade on **all six** databases (ER9). Set
`biz_debrand.product_name` on `rize` only; leave every other database alone and say so.

Chrome MCP is pre-approved: prove E3-2 by opening the Rize backend and showing the coach
tour greeting the user by the right name. Shots to `docs/handovers/errors_e3_shots/`.

Report back: each item done/partly/not with the reason; test results plus the full-suite
verdict line for every module touched; the six databases' versions and content hashes;
which `debrand_text` call sites you enabled the product rule for; screenshots; new
gotchas as `ER20`+; and anything unfinished, named. One commit per item, explicit
staging, **do not push**.
