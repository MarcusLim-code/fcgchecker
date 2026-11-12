"""Compatibility import for :mod:`fcgc.integrations.devin_agent`; edit that module instead."""

import sys

import fcgc.integrations.devin_agent as _implementation

sys.modules[__name__] = _implementation
