"""Compatibility import for :mod:`fcgc.retrieval.planned_retrieval`; edit that module instead."""

import sys

import fcgc.retrieval.planned_retrieval as _implementation

sys.modules[__name__] = _implementation
