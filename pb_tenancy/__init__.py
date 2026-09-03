# -*- coding: utf-8 -*-
# `tests` is NOT imported here: the framework discovers the package on its own
# when tests are enabled, and importing it in normal operation would load a
# suite into every customer's registry for nothing.
from . import models
from . import controllers
