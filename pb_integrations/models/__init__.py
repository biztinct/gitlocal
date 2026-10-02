# -*- coding: utf-8 -*-
from . import pb_integrations
# Extends `pb.integrations`, so it MUST import after the model that declares
# it — the registry builds classes in import order (W84's family).
from . import rule_composer
from . import pb_onboarding
