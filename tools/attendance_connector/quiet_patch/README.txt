PAYOBOOK - QUIET SCHEDULED SYNC PATCH

Try this on Ngoc Hoai Linh Dang's PC first.

1. Sign in as the Windows user who installed and paired the connector.
   IT can assist in that session. Do not run as a different administrator.
2. Download the ZIP. Right-click it and choose Extract All.
3. Open the extracted folder. Double-click Fix-Quiet-Sync.cmd.
4. Read the result message and click OK.
5. Keep the PC awake and the user signed in for 20 minutes. Confirm no
   command window appears at the next scheduled run. Tell Payobook the PC
   owner's name and when you applied the patch so we can check the upload.
6. After the pilot succeeds, repeat on the other PCs under each original user.

A command window may open while you apply this patch; this is expected.
The patch stops future scheduled launches from opening a command window.
An already-running sync is not interrupted. Its window may remain until it ends.

WHAT CHANGES
Only the existing task's program changes from python.exe to pythonw.exe.
The account, schedule, arguments, conditions and enabled/disabled state remain.
The connector, MDB, pairing and queued records are not replaced or changed.
No new pairing code, Payobook login or reinstall is required.
The patch does not upgrade the connector version.

The patch saves the previous task definition in the connector's data folder
before changing it. A PC already using pythonw.exe is left unchanged.
If IT customised the action or uses another account, the patch stops and asks
for IT help. If security software blocks it, IT should review and approve it
under company policy. Do not disable protection.

IT ROLLBACK
In Task Scheduler, open Payobook Attendance Connector / Properties / Actions.
Change only pythonw.exe back to python.exe, keeping the full folder path.
The task XML backup is under %LOCALAPPDATA%\PayobookAttendance\data.
It does not contain the Windows account's password.

This patch cannot confirm that a sync reached Payobook. That is checked from
the latest contact and database-read times on the Payobook setup page.
