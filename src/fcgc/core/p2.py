"""Compatibility import for :mod:`fcgc.checking.reduced_context`; edit that module instead."""

import sys

import fcgc.checking.reduced_context as _implementation

sys.modules[__name__] = _implementation
