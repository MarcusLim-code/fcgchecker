"""Compatibility import for :mod:`fcgc.retrieval.baseline`; edit that module instead."""

import sys

import fcgc.retrieval.baseline as _implementation

sys.modules[__name__] = _implementation
