#!/bin/bash
# FS-11/FS-12: Form builder counts (fsd) + My Payobook ticks + the page. Read-only.
db=$1
bash /tmp/fsd_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "x_portal_ticks: $(q "select count(*) filter (where portal_show)||' shown '||count(*) filter (where portal_edit)||' changeable' from pb_form_field_meta")"
echo "x_page_layouts: $(q "select count(*) from pb_form_layout where host_key='my_profile_page'")"
echo "profile_requests: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state)::text, chr(10) order by id),'')) from pb_profile_change_request")"
echo "detail_requests: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state)::text, chr(10) order by id),'')) from pb_me_detail_request")"
