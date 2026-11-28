#!/bin/bash
# usage: checksums.sh <copydb> <tag>  → /tmp/bg1w3c/<copydb>-<tag>.sums (read-only)
set -euo pipefail
DB=$1; TAG=$2
case "$DB" in bg1w3c_*) ;; *) echo "copies only"; exit 2;; esac
OUT=/tmp/bg1w3c/$DB-$TAG.sums
: > "$OUT"
for T in hr_employee res_partner_bank hr_version hr_contract hr_payslip hr_payslip_line hr_payslip_run res_partner res_bank; do
  if sudo -u postgres psql -Atq -d "$DB" -c "select to_regclass('public.$T') is not null" | grep -q t; then
    sudo -u postgres psql -Atq -d "$DB" -c "select '$T', count(*), md5(coalesce(string_agg(md5(t::text), '' order by id), '')) from $T t" >> "$OUT"
  fi
done
# hr_employee per row WITHOUT the four bank-file fields and the write stamps
sudo -u postgres psql -Atq -d "$DB" -c "select 'hr_employee_nobank', count(*), md5(coalesce(string_agg(md5((to_jsonb(t) - 'vietnam_bank_name' - 'vietnam_bank_branch' - 'vietnam_bank_account_name' - 'vietnam_bank_account_number' - 'write_date' - 'write_uid')::text), '' order by id), '')) from hr_employee t" >> "$OUT"
cat "$OUT"
