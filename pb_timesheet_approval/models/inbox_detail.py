# -*- coding: utf-8 -*-
"""Nothing lives here. The two hooks the inbox uses are generic and are
declared on the adapter mixin (`_approval_card_count`, `_approval_detail`);
`pb.timesheet.packet` implements both. This file is kept as the place a future
timesheet-only inbox shaping would go, and imports nothing so it cannot drift
into being a second vocabulary.
"""
