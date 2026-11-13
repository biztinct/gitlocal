"""Fail-closed age retention shared by scheduled and post-backup pruning."""
from datetime import timedelta


def expired_backup_ids(rows, now, keep_days):
    """Rows are (id, created_at, kind); always keep the newest usable backup."""
    if not isinstance(keep_days, int) or isinstance(keep_days, bool) or keep_days < 1:
        return []
    ordered = sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)
    cutoff = now - timedelta(days=keep_days)
    return [rid for rid, created, kind in ordered[1:]
            if created < cutoff and kind != 'final']
