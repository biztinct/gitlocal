#!/bin/bash
# Installed state + version of the modules this release touches or needs, on the five databases.
for db in payobook payobook_template p0clone rize sudima; do
  echo "$db: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_form_studio','pb_form_studio_people','pb_form_studio_contracts','pb_form_studio_reach','pb_form_studio_lists','pb_form_studio_explorer','pb_me_portal','pb_me_details','pb_form_studio_portal','biz_deroute','website')")"
  echo "  companies $(sudo -u postgres psql -X -At -d $db -c "select count(*) from res_company") page-layout $(sudo -u postgres psql -X -At -d $db -c "select count(*) from pb_form_layout where host_key='my_profile_page'")"
done
