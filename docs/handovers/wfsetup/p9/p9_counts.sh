#!/bin/bash
# WFSETUP P9 (copy of ../p7/p7_counts.sh + every clock connection's state and "Send accepted records to
# attendance" tick, which this release must NOT change). Read-only. "live_" lines move on their own.
db=$1
bash /tmp/p7_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "clock_switches: $(q "select coalesce(string_agg(id||':'||state||':'||publish_punches::text||':'||(token_hash is not null)::text, ' ' order by id),'none') from pb_clock_connector")"
echo "live_clock_events: $(q "select count(*)||' max '||coalesce(max(id),0)||' '||coalesce((select string_agg(state||'='||n, ',' order by state) from (select state, count(*) n from pb_clock_connector_event group by 1) s),'') from pb_clock_connector_event")"
