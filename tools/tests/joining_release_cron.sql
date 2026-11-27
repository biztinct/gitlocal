-- Run with psql on an isolated test database. Both tables live only for this transaction.
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE ir_cron(id integer PRIMARY KEY, active boolean);
INSERT INTO ir_cron VALUES (1,true),(2,false);
CREATE TEMP TABLE pb_release_previous_cron AS SELECT * FROM ir_cron;
UPDATE ir_cron SET active = NOT active;
INSERT INTO ir_cron VALUES (3,true),(4,false);
\ir ../../ops/joining/restore-cron.sql
\ir ../../ops/joining/restore-cron.sql
DO $$
BEGIN
    IF (SELECT array_agg(active ORDER BY id) FROM ir_cron) <> ARRAY[true,false,true,false] THEN
        RAISE EXCEPTION 'The previous job states or the install defaults changed';
    END IF;
END $$;
ROLLBACK;
