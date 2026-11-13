PAYOBOOK ATTENDANCE CONNECTOR 1.0.1 — WINDOWS PILOT PACKAGE

What it does
Reads CheckInOut from a local Mitaco MDB, queues new records and uploads them
through HTTPS. Staff continue their manual terminal downloads in Mitaco.
No inbound port, terminal reconfiguration or client-hosted web service needed.
It never changes the MDB. No fingerprint or face templates are uploaded.

Where to start
1. In Payobook: Workforce > Time > Time clocks > Data connectors.
2. Create the source. Use one shared source-group name for PCs covering the
   same terminals; different groups for different terminal collections.
3. Select time zone, earliest history date and employee-code field. Leave
   attendance processing OFF for the initial extraction test. Sync still runs.
4. On the WINDOWS PC, open that Payobook page in a browser and download the
   Windows package. The website also opens on a Mac, but this package installs
   on Windows 11 x64. You can transfer the ZIP from the Mac if easier.
5. Extract all files. IT reviews/approves the package and PowerShell policy,
   then runs Install.cmd. Do not disable antivirus or organisation policy.
6. Browse to the local MDB. Test read-only access. In Payobook generate a
   30-minute pairing code, then enter it and the HTTPS website in Windows setup.
7. Pair, then Sync now. Payobook shows last contact, last read and received rows.
8. Enable scheduled sync. The task checks every 5 minutes; Payobook's configured
   interval (default 15 minutes) governs database scans. A locked screen is OK.

Unattended operation
Default task runs while the setup user is signed in. For logged-off operation,
IT opens Windows task settings, edits "Payobook Attendance Connector", selects
"Run whether user is logged on or not", and enters that SAME Windows account's
password in Windows. Do NOT use S4U/"Do not store password" or a different user:
network access and per-user encrypted credentials would not be available.
The account needs read access to the MDB and outbound HTTPS to Payobook.
The computer must be awake. Test one full run after logging off. If a Windows
password changes, IT updates the scheduled task. Payobook never stores it.
This is a scheduled application, not a Windows Service.

Data and recovery
- Identical raw rows are uploaded once. Repeat delivery is acknowledged safely.
- Changed/invalid rows arrive in Payobook for review without stopping later rows.
- Older punches downloaded late are found by full scans from the history date.
- Future backfills: change history date in Payobook; allow a sync to pick up the
  configuration, then the next scan covers the new range.
- Rescan history removes only acknowledged local fingerprints, not pending rows.
- No "latest version wins" guesses: this schema has no reliable modification ID.
- Source edits appear as additional records; deletions do not erase Payobook
  attendance. This release does not automatically detect deleted source rows.
- Data corrections are investigated in Received records / Time clocks. An
  unknown employee or missing punch does not stop the connector.
- Revoking installation access is for security/retirement, not data cleanup.
- Internet outages retain the local queue; a successful later run catches up.
- File locked/changing: it retries later and still sends already queued records.
- Same source group deduplicates overlapping PC data in the punch ledger.
  Physical terminal attribution is not inferred from ambiguous MachineNo.
- Only allowlisted punch fields leave the PC. Credentials and pending payloads
  use Windows CurrentUser DPAPI; installation folder permissions restrict access.
- Database password/encrypted MDB variants are not supported by this adapter.
  Do not remove database security; ask IT about a supported read-only export.

Local installation
%LOCALAPPDATA%\PayobookAttendance
Desktop shortcut opens setup/status. status.json contains diagnostics without
punch details or secrets. Queue is SQLite, source snapshots are temporary.
Uninstall: remove scheduled task through Windows Task Scheduler. Preserve the
installation's data folder until pending rows are acknowledged, then IT can
remove the folder and shortcut. No source database is ever removed.

Testing
Mac can test extraction and API delivery with PAYOBOOK_LOCAL_TEST=1; that mode
is a local test harness without Windows DPAPI and is not a deployed agent.
Before live use, test this package on Windows, then pilot alongside Mitaco.
The Python runtime is from python.org. This pilot's PowerShell scripts are
not Authenticode-signed. IT must review them under its own software policy.
Dependency licences are included. Build inputs are pinned by SHA-256.

Build sources
Python embeddable runtime: https://www.python.org/ftp/python/3.13.12/
Read-only Access parser: https://github.com/claroty/access_parser
Construct / Tabulate: pinned PyPI packages, bundled with their licences.
No customer database, employee data or installation token is in the ZIP.

Updating an existing installation
Wait for any sync to finish and close setup. Download and extract the new ZIP,
then run Install.cmd under the SAME Windows account. Pairing, preferences and
queued records in the data folder are preserved. Do not generate another code
or pair again. The updated setup shows Connector 1.0.1 and animated activity
with elapsed time. Results are summaries; Show diagnostics displays technical
details. Check connection on the website reads server status; it does not
remotely start a Windows sync.
