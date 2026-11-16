-- WDGAP S8-D (EX1) — READ-ONLY check, one database at a time.
--
-- People whose CURRENT contract (the running one) followed an earlier contract
-- and does NOT have pay lines (allowances) that the earlier contract had —
-- the renewals made before S8-D, which started without the old contract's
-- pay lines. Nothing is changed by this query; the owner decides what to do.
--
-- "Followed an earlier contract" = linked by the contract decisions board
-- (`pb_renewed_from_id`), or else the person's previous contract that ended at
-- most 31 days before the current one started (the Contracts "Renew" button
-- does not write the link).
-- "Lost a line" = the earlier contract has a pay line with an amount (or a
-- text value) and the current contract has no line for that pay item, or has
-- it at 0 with no text.
--
-- Run:  sudo -u postgres psql -d <db> -f renewal_lost_pay_lines.sql
-- (or `psql -d <db> -At -F ',' -f …` for a CSV-like listing).
BEGIN TRANSACTION READ ONLY;

WITH cur AS (
    SELECT DISTINCT ON (c.employee_id)
           c.id, c.employee_id, c.date_start, c.company_id, c.pb_renewed_from_id
      FROM hr_contract c
     WHERE c.state = 'open'
     ORDER BY c.employee_id, c.date_start DESC, c.id DESC
), pairs AS (
    SELECT cur.id AS cur_id, cur.employee_id, cur.company_id, cur.date_start,
           COALESCE(cur.pb_renewed_from_id, (
               SELECT p.id
                 FROM hr_contract p
                WHERE p.employee_id = cur.employee_id
                  AND p.id <> cur.id
                  AND p.date_start < cur.date_start
                  AND p.date_end IS NOT NULL
                  AND p.date_end >= cur.date_start - 31
                ORDER BY p.date_start DESC, p.id DESC
                LIMIT 1)) AS prev_id,
           (cur.pb_renewed_from_id IS NOT NULL) AS linked
      FROM cur
), lost AS (
    SELECT pairs.*, t.code, a.amount, a.text_value
      FROM pairs
      JOIN hr_contract_advantage a ON a.contract_id = pairs.prev_id
      JOIN hr_contract_advantage_template t ON t.id = a.advantage_template_id
     WHERE pairs.prev_id IS NOT NULL
       AND (COALESCE(a.amount, 0) <> 0 OR COALESCE(a.text_value, '') <> '')
       AND NOT EXISTS (
           SELECT 1 FROM hr_contract_advantage n
            WHERE n.contract_id = pairs.cur_id
              AND n.advantage_template_id = a.advantage_template_id
              AND (COALESCE(n.amount, 0) <> 0 OR COALESCE(n.text_value, '') <> ''))
)
SELECT co.name                         AS company,
       e.name                          AS person,
       lost.cur_id                     AS current_contract,
       lost.date_start                 AS current_start,
       lost.prev_id                    AS earlier_contract,
       CASE WHEN lost.linked THEN 'board' ELSE 'by dates' END AS how_linked,
       count(*)                        AS lines_lost,
       string_agg(lost.code || ' ' || COALESCE(NULLIF(lost.text_value, ''),
                  to_char(lost.amount, 'FM999G999G999G990D99')), '; '
                  ORDER BY lost.code) AS lines
  FROM lost
  JOIN hr_employee e ON e.id = lost.employee_id
  LEFT JOIN res_company co ON co.id = lost.company_id
 GROUP BY co.name, e.name, lost.cur_id, lost.date_start, lost.prev_id, lost.linked
 ORDER BY co.name, e.name;

ROLLBACK;
