"""Compatibility import for :mod:`fcgc.retrieval.benchmark`; edit that module instead."""

import sys

import fcgc.retrieval.benchmark as _implementation

sys.modules[__name__] = _implementation
