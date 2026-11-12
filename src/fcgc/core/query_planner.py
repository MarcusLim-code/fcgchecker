"""Compatibility import for :mod:`fcgc.retrieval.query_planner`; edit that module instead."""

import sys

import fcgc.retrieval.query_planner as _implementation

sys.modules[__name__] = _implementation
