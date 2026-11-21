#!/bin/bash
# FS-15: the FS-12 counts + the Form builder's standard-field settings rows (counts and one md5,
# never values). Read-only. The new column exists only after the upgrade (0 before).
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
has=$(q "select count(*) from information_schema.columns where table_name='pb_form_field_meta' and column_name='std_show'")
if [ "$has" = 1 ]; then
  echo "x_showfor: shown-for $(q "select count(*) from pb_form_field_meta where std_show is not null") older-hide $(q "select count(*) from pb_form_field_meta where std_hidden")/$(q "select count(*) from pb_form_field_meta_std_country_rel") labels $(q "select count(*) from pb_form_field_meta where std_labels is not null")"
else
  echo "x_showfor: shown-for 0 older-hide $(q "select count(*) from pb_form_field_meta where std_hidden")/$(q "select count(*) from pb_form_field_meta_std_country_rel") labels $(q "select count(*) from pb_form_field_meta where std_labels is not null")"
fi
echo "x_meta_rows: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, name, portal_show, portal_edit, std_hidden, std_labels::text)::text, chr(10) order by id),'')) from pb_form_field_meta")"
