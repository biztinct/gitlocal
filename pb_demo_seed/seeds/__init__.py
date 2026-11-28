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
        # THE KEY IS ENGINEERING, THE LABEL IS THE SCREEN. The key is stored
        # in a `noupdate` row on every database that has ever loaded this
        # world, so renaming it would orphan those panels; the label is what a
        # person reads and carries no customer's name.
        'label': 'DEMO Vietnam — five people, five stories',
        'builders': [
            org.build,
            people.build,
            programs.build,
            assets.build,
            journeys.build,
            contracts_exits.build,
        ],
    },
    # NO BUILDERS ON PURPOSE. This world is not built, it is adopted: the
    # records already exist because the product made them while somebody was
    # testing a screen, and `pb.demo.seed.register()` hands them over. It is
    # still a world for the removal's purposes — one register, one backwards
    # walk, one button.
    'adopted': {
        'label': 'Records adopted from the product',
        'builders': [],
    },
}
