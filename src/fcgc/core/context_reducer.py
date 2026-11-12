"""Compatibility import for :mod:`fcgc.checking.context_reducer`; edit that module instead."""

import sys

import fcgc.checking.context_reducer as _implementation

sys.modules[__name__] = _implementation
