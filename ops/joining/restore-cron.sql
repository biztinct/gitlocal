-- Only restore jobs which existed before the upgrade. New jobs keep their install setting.
UPDATE ir_cron AS job
SET active = previous.active
FROM pb_release_previous_cron AS previous
WHERE job.id = previous.id AND job.active IS DISTINCT FROM previous.active;
