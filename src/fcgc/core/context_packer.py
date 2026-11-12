"""Compatibility import for :mod:`fcgc.checking.context_packer`; edit that module instead."""

import sys

import fcgc.checking.context_packer as _implementation

sys.modules[__name__] = _implementation
