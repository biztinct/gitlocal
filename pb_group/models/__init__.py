# -*- coding: utf-8 -*-
# `pb.fx` first: `pb.group` names its policies and the facade calls it.
from . import pb_fx
from . import pb_group
from . import pb_division
from . import res_company
# `pb.group.visibility` before the facade: the facade's own reads go through it.
from . import pb_group_visibility
from . import pb_group_room
