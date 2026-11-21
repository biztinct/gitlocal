# -*- coding: utf-8 -*-
"""The PayAI Action catalogue: registry, gate, resolvers, Actions, runner.

Importing this package registers every Action (the decorator fills
`registry.ACTIONS` at import time), so the catalogue is complete before any
model method can ask for it.
"""
from . import registry
from . import gate
from . import resolve
from . import cards
from . import actions_green
from . import actions_amber
from . import actions_red
from . import actions_stubs
from . import runner
