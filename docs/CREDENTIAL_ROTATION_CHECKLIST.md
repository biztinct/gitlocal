# Credential rotation — what is exposed and what to change

Written 2026-09-11. **No secret, old or new, may be written into this file or any other
file in this repository** (standing rule, see commit `a2553ef1`).

## Why rewriting git history does not remove the need

Every value below was **pushed to a public repository months or weeks ago**. The
working tree is clean now, but the exposure already happened. Dates are the first
commit on `origin/19.1` that carried each value:

| Value | Public since | Days public as of 2026-09-11 |
|---|---|---|
| Zoho client secret + client id + auth code | 2025-06-22 (`64f14b7c`) | 446 |
| `{withheld: apex-admin-2026-08}` | 2026-07-20 (`72cd2bd8`) | 53 |
| `{withheld: abm-admin}` | 2026-08-26 (`47a361cb`) | 16 |
| `{withheld: rize-admin}` | 2026-09-01 (`75836608`) | 10 |

Rewriting the 90 unpushed commits changes nothing, because none of these values came
from those commits — they came from commits already on GitHub. A **full** history
rewrite plus a force push would clear the current branch, and still would not help:

* GitHub keeps detached commits reachable by their SHA after a force push, and does not
  guarantee when they are collected.
* Forks and existing clones are untouched by anything done to this repository.
* Public repositories are continuously scraped by automated credential harvesters. A
  secret that sat in a public repo for 446 days must be treated as compromised, not as
  possibly-unnoticed.

**Changing the credentials is the only step that closes them.** Everything else is
tidying.

---

## 1. The connector key — do this one first

The Zoho OAuth application's **client secret** has been public for over a year. It is
not a password on a system we control, so it cannot be changed from here.

* Sign in to the Zoho API console for the account that owns the "Self Client"
  application used by the legacy HR integration.
* **Regenerate the client secret**, or delete the application and create a new one.
* The old authorization code is single-use and long expired; nothing needs doing to it.
* Put the new values in **Settings → Technical → System Parameters** as
  `zoho.client_id`, `zoho.client_secret`, `zoho.auth_code`. The code reads them from
  there now (`om_hr_payroll/models/hr_zoho_staging.py`, from 19.0.1.4.0). Do not put
  them in a file.

## 2. The admin login

`ash@biztinct.com` is active on **five databases** and its password differs between
them. All of these were published:

| Database | Is the login active | Published password |
|---|---|---|
| `payobook` (live) | yes | `{withheld: apex-admin-2026-08}`, and an older one |
| `abm` (live) | yes | `{withheld: abm-admin}` |
| `rize` (live tenant) | yes | `{withheld: rize-admin}` |
| `p9clone` | yes | as per `payobook` |
| `rztest` | yes | as per `rize` |
| `payobook_template` | no such login | — |

Change it on each one, through **Settings → Users** or the user's own preferences.
Use a different password per database, as now. Do not reuse any published value or an
obvious variant of one.

`lan@acme.com` was documented as sharing the `abm` password. If that login still exists
on any database, change it too.

## 3. The demo and test logins

Published, and active on `payobook` and `p9clone`:

* `demo@payobook.com`
* `ess1.demo@payobook.com` … `ess9.demo@payobook.com`
* `igc1.validator` (on `p9clone`)

These are demo actors rather than staff, so the risk is lower — but they are real logins
on a live database and several carry employee records. Change them, or deactivate the
ones no longer used. `igc1.validator` was flagged in an earlier ledger as a temporary
account that should have been deactivated.

## 4. After changing them

* Do **not** record the new values in this repository. If a handover needs to say which
  credential it means, use the `{withheld: <label>}` form the documents now use.
* Consider whether this repository needs to stay public at all. It carries the complete
  source of the product, not only these values. The owner's decision on 2026-09-11 was
  to keep it public.
* GitHub's secret-scanning alerts are worth switching on for the repository regardless:
  Settings → Code security → Secret scanning. It will flag the next one before a human
  notices.
