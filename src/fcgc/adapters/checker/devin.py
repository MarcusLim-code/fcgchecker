"""Compatibility import for :mod:`fcgc.integrations.devin`; edit that module instead."""

import sys

import fcgc.integrations.devin as _implementation

sys.modules[__name__] = _implementation
