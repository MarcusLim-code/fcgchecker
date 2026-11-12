"""Legacy import; use :mod:`fcgc.integrations.placeholder_checker`."""

import sys

import fcgc.integrations.placeholder_checker as _implementation

sys.modules[__name__] = _implementation
