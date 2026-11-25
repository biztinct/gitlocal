#!/bin/bash
# WFSETUP P8: read-only fingerprint of EVERY table of one database: "table rows max_id max_write_date".
# Two fingerprints diffed = every table the clock-in switch wrote to (inserts, deletes, plain writes).
# Root: bash p8_tables.sh <db> > file
db=$1
sudo -u postgres psql -X -At -d "$db" <<'SQL' | sudo -u postgres psql -X -At -d "$db" | sort
select format('select %L||'' ''||count(*)||'' ''||%s||'' ''||%s from %I;', t.table_name,
  case when exists (select 1 from information_schema.columns c where c.table_schema='public' and c.table_name=t.table_name and c.column_name='id' and c.data_type in ('integer','bigint')) then 'coalesce(max(id),0)' else '''-''' end,
  case when exists (select 1 from information_schema.columns c where c.table_schema='public' and c.table_name=t.table_name and c.column_name='write_date') then 'coalesce(max(write_date)::text,''-'')' else '''-''' end,
  t.table_name)
from information_schema.tables t where t.table_schema='public' and t.table_type='BASE TABLE' order by 1;
SQL
