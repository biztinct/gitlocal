#!/bin/bash
# WFSETUP P8 UNDO: put the clock-ins back the way they were before "Switch clock-ins on", from the baseline
# p8_baseline.sh took right before the switch. ONE transaction: all or nothing.
#   - received clock records: every record in the baseline gets its exact state, note, punch link, write
#     date and write user back; a record that arrived AFTER the baseline and was sent to attendance goes
#     back to "Ready" with the note a switched-off clock writes
#   - punches made from those records and the time-clock attendance rows made from them are removed
#     (only rows newer than the baseline: device rows of the pairing job, never a row a person made,
#     never a row the rules calculation made)
#   - the clocks' send switch and collection machine go back to the baseline; collection machines made by
#     the switch are removed; the "switched on" chatter lines on those clocks are removed
#   - the "created" / tracking chatter lines the attendance app wrote on those attendance rows, and the
#     "check-out missing" attention items the clock watcher raised for them, are removed; each person's
#     last check-in / check-out / last attendance row go back to the baseline
#   - pb_clock.* system parameters go back to the baseline; the job wake-up rows the switch queued are removed
# The connector process job and the pairing job must not be mid-run: on LIVE, switch the clocks off (on
# screen) and wait one job cycle first. Root: bash p8_undo.sh <db> <baseline folder> [--dry-run]
set -eu
db=$1; B=$2; MODE=${3:-}
[ -s $B/tables.txt ] && [ -s $B/events.csv ] && [ -s $B/connectors.csv ] && [ -s $B/employees.csv ] || { echo "baseline incomplete"; exit 1; }
maxid() { awk -v t="$1" '$1==t {print $3}' $B/tables.txt; }
P_MAX=$(maxid pb_clock_punch); A_MAX=$(maxid hr_attendance); D_MAX=$(maxid pb_clock_device)
M_MAX=$(maxid mail_message); T_MAX=$(maxid ir_cron_trigger); OL_MAX=$(maxid hr_attendance_overtime_line); AL_MAX=$(maxid pb_clock_alert)
CONNS=$(cut -d, -f1 $B/connectors.csv | paste -sd, -)
END=COMMIT; [ "$MODE" = --dry-run ] && END=ROLLBACK
# the baseline folder is root-only: hand psql a private copy of the four lists, removed afterwards
R=$(mktemp -d); cp $B/events.csv $B/connectors.csv $B/params.csv $B/employees.csv $R/; chown -R postgres $R; chmod 700 $R
trap 'rm -rf $R' EXIT
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d "$db" <<SQL
BEGIN;
CREATE TEMP TABLE ev_base (id int primary key, state varchar, note text, punch_id int, write_date timestamp, write_uid int);
\copy ev_base from '$R/events.csv' with csv
CREATE TEMP TABLE conn_base (id int primary key, publish_punches boolean, device_id int, write_date timestamp, write_uid int);
\copy conn_base from '$R/connectors.csv' with csv
CREATE TEMP TABLE par_base (id int, key varchar, value text, write_date timestamp, write_uid int);
\copy par_base from '$R/params.csv' with csv
CREATE TEMP TABLE emp_base (id int primary key, last_attendance_id int, last_check_in timestamp, last_check_out timestamp, write_date timestamp, write_uid int);
\copy emp_base from '$R/employees.csv' with csv
-- two referencing columns have no index: without these the foreign-key checks of the deletes below scan
-- 71k records per removed punch (minutes per thousand). Made and dropped inside this transaction.
CREATE INDEX p8_undo_ev_punch ON pb_clock_connector_event (punch_id);
CREATE INDEX p8_undo_roster_att ON hr_shift_planning (pb_attendance_id);
-- 1. received records
UPDATE pb_clock_connector_event e SET state=b.state, note=b.note, punch_id=b.punch_id, write_date=b.write_date, write_uid=b.write_uid
  FROM ev_base b WHERE b.id=e.id AND (e.state, coalesce(e.note,''), coalesce(e.punch_id,0)) IS DISTINCT FROM (b.state, coalesce(b.note,''), coalesce(b.punch_id,0));
UPDATE pb_clock_connector_event SET state='ready', punch_id=NULL,
  note='Received. Attendance processing is not enabled for this source.'
  WHERE id > (SELECT coalesce(max(id),0) FROM ev_base)
    AND (state IN ('posted','duplicate') OR (state='review' AND note LIKE 'Same employee and time with different source attributes%'));
-- 2. punches newer than the baseline (they point at attendance rows: remove them first)
CREATE TEMP TABLE gone_att AS SELECT id FROM hr_attendance WHERE id > $A_MAX AND pb_entry_source='device' AND pb_policy_roster_id IS NULL;
UPDATE pb_clock_connector_event SET punch_id=NULL WHERE punch_id > $P_MAX;
DELETE FROM pb_clock_punch WHERE id > $P_MAX;
-- 3. time-clock attendance rows newer than the baseline, what the attendance app made for them (extra-hours
--    lines of those people and days, chatter lines), the watcher's per-person attention items, and each
--    person's last check-in / check-out
DELETE FROM hr_attendance_overtime_line l WHERE l.id > $OL_MAX AND EXISTS (SELECT 1 FROM hr_attendance a JOIN gone_att g ON g.id=a.id
  WHERE a.employee_id=l.employee_id AND l.date BETWEEN (a.check_in - interval '1 day')::date AND (coalesce(a.check_out, a.check_in) + interval '1 day')::date);
DELETE FROM mail_message WHERE model='hr.attendance' AND res_id IN (SELECT id FROM gone_att);
DELETE FROM pb_clock_alert WHERE id > $AL_MAX AND kind IN ('auto_closed','held','backlog');
UPDATE hr_employee e SET last_attendance_id=b.last_attendance_id, last_check_in=b.last_check_in, last_check_out=b.last_check_out,
  write_date=b.write_date, write_uid=b.write_uid FROM emp_base b
  WHERE b.id=e.id AND (e.last_attendance_id IN (SELECT id FROM gone_att) OR (e.last_attendance_id, e.last_check_in, e.last_check_out) IS DISTINCT FROM (b.last_attendance_id, b.last_check_in, b.last_check_out));
DELETE FROM hr_attendance WHERE id IN (SELECT id FROM gone_att);
-- 4. the clocks
UPDATE pb_clock_connector c SET publish_punches=b.publish_punches, device_id=b.device_id, write_date=b.write_date, write_uid=b.write_uid
  FROM conn_base b WHERE b.id=c.id;
DELETE FROM pb_clock_alert WHERE id > $AL_MAX AND device_id IN (SELECT id FROM pb_clock_device WHERE id > $D_MAX AND kind='collection');
DELETE FROM pb_clock_device WHERE id > $D_MAX AND kind='collection' AND id NOT IN (SELECT device_id FROM pb_clock_punch);
DELETE FROM mail_message m WHERE m.id > $M_MAX AND m.model='pb.clock.connector' AND m.res_id IN ($CONNS)
  AND EXISTS (SELECT 1 FROM mail_tracking_value v JOIN ir_model_fields f ON f.id=v.field_id
              WHERE v.mail_message_id=m.id AND f.model='pb.clock.connector' AND f.name='publish_punches');
-- 5. parameters + queued wake-ups of the two clock jobs
DELETE FROM ir_config_parameter WHERE key LIKE 'pb_clock.%' AND id NOT IN (SELECT id FROM par_base);
UPDATE ir_config_parameter p SET value=b.value, write_date=b.write_date, write_uid=b.write_uid FROM par_base b WHERE b.id=p.id;
DELETE FROM ir_cron_trigger WHERE id > $T_MAX AND cron_id IN (SELECT res_id FROM ir_model_data WHERE model='ir.cron'
  AND module='pb_clock' AND name IN ('cron_process_connector','cron_pair_punches'));
DROP INDEX p8_undo_ev_punch; DROP INDEX p8_undo_roster_att;
SELECT 'after undo: events '||(SELECT string_agg(state||'='||n, ' ') FROM (SELECT state, count(*) n FROM pb_clock_connector_event GROUP BY 1 ORDER BY 1) s)
  ||' | punches '||(SELECT count(*) FROM pb_clock_punch)||' | attendance '||(SELECT count(*) FROM hr_attendance)
  ||' | switches on '||(SELECT count(*) FROM pb_clock_connector WHERE publish_punches)
  ||' | extra-hours lines '||(SELECT count(*) FROM hr_attendance_overtime_line)||' | attention items '||(SELECT count(*) FROM pb_clock_alert)
  ||' | collection machines '||(SELECT count(*) FROM pb_clock_device WHERE kind='collection') AS result;
$END;
SQL
echo "undo $([ "$END" = COMMIT ] && echo COMMITTED || echo 'DRY RUN rolled back') on $db from $B"
