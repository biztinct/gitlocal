#!/bin/bash
# WFSETUP P8: what the undo needs, taken right BEFORE the clocks are switched on. Read-only.
#   tables.txt       every table: rows, max id, max write date (p8_tables.sh) - the undo deletes ids above these
#   events.csv       every received clock record: id, state, note, punch, write date, write user
#   connectors.csv   the six PC clocks: id, send switch, collection machine, write date, write user
#   params.csv       pb_clock.* system parameters (the pairing job keeps its last runs there)
#   employees.csv    each person's last check-in / check-out / last attendance row (the attendance app keeps them)
# Root: bash p8_baseline.sh <db> <folder>
set -eu
db=$1; out=$2
mkdir -p $out; chmod 700 $out
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 -d "$db" "$@"; }
bash /tmp/p8_tables.sh $db > $out/tables.txt
pq -c "\copy (select id, state, note, punch_id, write_date, write_uid from pb_clock_connector_event order by id) to stdout with csv" > $out/events.csv
pq -c "\copy (select id, publish_punches, device_id, write_date, write_uid from pb_clock_connector order by id) to stdout with csv" > $out/connectors.csv
pq -c "\copy (select id, last_attendance_id, last_check_in, last_check_out, write_date, write_uid from hr_employee order by id) to stdout with csv" > $out/employees.csv
pq -c "\copy (select id, key, value, write_date, write_uid from ir_config_parameter where key like 'pb_clock.%' order by id) to stdout with csv" > $out/params.csv
echo "$(date -u +%FT%TZ) baseline of $db: tables $(wc -l < $out/tables.txt), events $(wc -l < $out/events.csv), connectors $(wc -l < $out/connectors.csv) ($(cut -d, -f2 $out/connectors.csv | sort | uniq -c | tr '\n' ' ')), params $(wc -l < $out/params.csv), employees $(wc -l < $out/employees.csv)" | tee $out/baseline.log
