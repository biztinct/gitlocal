# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Install hook — bring the EXISTING roster into the acknowledgment contract.

`action_publish` mints a token for the shifts it moves out of draft, which is
the right seam and it only ever sees the future. On a live tenant whose roster
was published before this module existed, that leaves every current shift with
no token — so the mailed confirmation link, the channel built for the people who
have no login, points at nothing. Nothing errors and no test can see it; the
live row count is what says so.

Idempotent and bounded (only shifts that can still be acknowledged), so a
reinstall is free and no credential is minted for a shift nobody can confirm.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    n = env['hr.shift.planning']._ess_backfill_tokens()
    _logger.info('pb_ess_workforce: minted acknowledgment tokens for %s '
                 'already-published shifts', n)
