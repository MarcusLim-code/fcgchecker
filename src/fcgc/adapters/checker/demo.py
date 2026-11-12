"""Compatibility import for :mod:`fcgc.integrations.synthetic_checker`; edit that module instead."""

import sys

import fcgc.integrations.synthetic_checker as _implementation

sys.modules[__name__] = _implementation
