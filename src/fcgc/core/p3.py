"""Compatibility import for :mod:`fcgc.retrieval.adaptive_retrieval`; edit that module instead."""

import sys

import fcgc.retrieval.adaptive_retrieval as _implementation

sys.modules[__name__] = _implementation
