# -*- coding: utf-8 -*-
"""The demo worlds, and the order their parts are built in.

ORDER IS NOT COSMETIC HERE. It is the only thing that makes the remove safe:
the register is walked backwards, so whatever is built last is removed first.
Organisation before people, people before the records that point at them,
stories last. Get this list right and no builder ever has to think about
deletion again.
"""

from . import org, people, assets, journeys, contracts_exits, programs

PROFILES = {
    'rize_vn': {
        'label': 'Rize Vietnam — five people, five stories',
        'builders': [
            org.build,
            people.build,
            programs.build,
            assets.build,
            journeys.build,
            contracts_exits.build,
        ],
    },
}
