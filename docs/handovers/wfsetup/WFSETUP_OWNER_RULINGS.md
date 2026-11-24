# WFSETUP — owner rulings (all given on cards, Sydney time)

2026-11-24 22:20
- R1 Codex has FINISHED with the Workforce screens — build freely, replace its setup screen. (Still read /opt/deploy-notes.md before deploying.)
- R2 Go live first on **sudima + payobook**; rize / payobook_template / p0clone follow in one batch when the owner says.
- R3 Trim the daily Workforce menu once setup has its own home: drop Shifts & patterns, Rules & calendars, Connections and the
  card-style People list from the unified workspace tabs; keep Overview, Roster, Timesheets, More. (P5)

2026-11-24 22:55
- R4 **Full late rules everywhere**: the detailed rules (`pb_attendance_policy`) are to be available on every site, not only
  Sudima. Owner note: "Rize is not using any rules for its pay calculations so no need to do testing there specifically."
  ⇒ `pb_workforce_setup` may hard-depend on `pb_attendance_policy` (from P2); the deploy installs it where missing.
  A policy only calculates once ACTIVATED, so installing it changes nothing until a customer confirms their rules.
- R5 Overtime stays **per shift** ("overtime starts N hours after the shift starts" — shown as a clock time on each shift).
  No change to the calculation model.
- R6 **No approval switch.** The screen says overtime always needs a manager's approval before it is paid.
- R7 **Holiday / rest-day pay becomes automatic**: when the roster is made, shifts on a public holiday or on the person's
  day off are marked for the holiday / rest-day rate; a single shift can still be changed by hand. Owner note: Sudima is in
  production but no real pay run has happened; anything there is test/demo. Test carefully, no long recompute rehearsal needed.
