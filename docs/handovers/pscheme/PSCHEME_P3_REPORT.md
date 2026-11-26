# PSCHEME P3 — report (merge, lessons, release x5, fill dry run)

## PAUSED (2026-11-26 12:05 UTC, coordinator instruction: owner pause until about 12:05 am Sydney)

**Done (read-only):**
- Read the P3 handover, the ledger (all three branches: PS0-PS9, PS-a1..a9, PS-b1..b8), the P1 / P2a / P2b
  reports, FACTS §10-§11, the NEWHIRE P8 report §6 and every `docs/handovers/newhire/p8/` script, the NEWHIRE
  ledger release gotchas.
- Read `/opt/deploy-notes.md` on the server (read only, nothing written): last entries are DOCSTUDIO CLOSE
  START 02:42 / DONE 02:53 / NOTE 03:03 UTC 26 Nov — no open START, no HOLD, no deploy lock file. Live `pb_learn`
  is 19.0.20.10.0 (DOCSTUDIO CLOSE), so the `origin/19.1` merge brings that version in.
- `origin/19.1` fetched: 19 commits ahead of `pscheme` (52108162c).

**Half-done:** nothing. No merge was started; the worktree is clean apart from this file.

**Not started:** A.1-A.4 (merges, tests, walks, sheet source, translations), B (lessons), C (release x5), D (fill
dry run), the client table under `outputs/`.

**Local servers / databases started:** none. **Server:** nothing written, no START line, no dumps, no lock.

**Next three steps on resume:**
1. Re-read `/opt/deploy-notes.md` (another session may have released during the pause), `git fetch origin 19.1`.
2. A.1: merge `pscheme-p2a`, then `pscheme-p2b` into `pscheme` (take both sides on appends; `pb_scheme_map`
   and `pb_hr_payroll_formula` manifests = higher version + one bump), then merge `origin/19.1`.
3. A.3 (sheet rows get their own `sheet` source, "Upload sheet") and A.4 (vi/id for the ~25 PS-a8 strings + the
   149 old `pb_scheme_map` id_ID msgids, parse gate), then the A.2 test run.
