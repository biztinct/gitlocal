#!/bin/bash
# FS-14: the FS-12 counts + the personal-box whitelist (pb_me_portal.editable_fields). Read-only.
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "profile_param: $(q "select coalesce((select value from ir_config_parameter where key='pb_me_portal.editable_fields'),'<unset>')")"
echo "page_row: $(q "select coalesce(string_agg(md5(coalesce(sections::text,'')||coalesce(page::text,'')||version::text), ' '),'none') from pb_form_layout where host_key='my_profile_page'")"
