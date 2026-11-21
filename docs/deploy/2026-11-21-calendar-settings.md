# Custom calendar settings — 21 November 2026

Implemented in `b9bd93d243b8fe1475a1942cf58ed2021961bba8`. Deployed combined release `f7b13c8a219fe13deedb9c42bfffdd879362c9a2` merges that local branch with `origin/19.1` (`ce098597a`). The isolated release checkout preserves both branches; unrelated working files were excluded.

Calendar providers now opens a custom Google/Microsoft configuration form directly. Personal Calendar → Connect has no master-settings link and uses a custom sign-in explanation before provider-hosted authentication. Personal passwords are never collected. Administrator APIs enforce system-administrator access, redact saved secrets, preserve blank secrets, validate inputs and reject stale saves. The legacy settings action now resolves to the custom client action.

Deployed on Payobook19v2 to `/odoo/odoo-server/addons`, serving payobook, payobook_template, p0clone, rize and the additionally active sudima database. No schema or manifest change; no module installation or schema upgrade needed. All 199 combined custom-addon trees and installed versions matched after release. The server-generated `pb_clock/releases/PayobookAttendanceConnector.zip` was preserved. Standard addons, ABM retirement archives, existing backups and other sessions' work were untouched.

The FS-14 scheduler was waiting between attempts. This release acquired the same exclusive `/tmp/payobook-studio-deploy.lock` throughout preflight, code replacement and restart; FS-14's addon was unchanged. Rollback source archive and release receipt remain at `/tmp/shared-calendar-settings-20261121` on the server.

Validation:

- Python and XML parsing, JavaScript syntax, and git diff checks passed.
- Staged regression: 49 tests, zero failures/errors.
- Deployed connection regression on p0clone: 25 tests, zero failures/errors; test transactions rolled back and outbound test email suppressed.
- HTTP 200: rize.payobook.com, payobook.com, p0clone.payobook.com, sudima.payobook.com login pages.
- Chrome on rize.payobook.com: Settings → Connect → Calendar providers opens the custom form directly; both provider cards render; pause draft reverts on Discard; empty Save shows required-field validation; Back returns to custom Connect settings; personal Calendar → Connect contains no master-settings links.
- Rize has no configured application credentials for either provider. Actual external account authorization was not attempted; the live screen correctly disables sign-in until administrator setup. No credentials were changed during UI checks.
- No screenshots or PNG files were saved by this test run; visual observations stayed in the computer-use tool output.
