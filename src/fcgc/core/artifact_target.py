"""Compatibility import for :mod:`fcgc.checking.function_scope`; edit that module instead."""

import sys

import fcgc.checking.function_scope as _implementation

sys.modules[__name__] = _implementation
