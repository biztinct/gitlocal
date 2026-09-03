# -*- coding: utf-8 -*-
# FLEET P2A — the tenant-side platform link.
from . import test_tenancy
# FLEET P4 — the feature switches, as this database reads them.
from . import test_features
# FLEET P5 — the plan, the employee limit and the paused door.
from . import test_standing
# FLEET P6 — support access, the door and the trail.
from . import test_support
