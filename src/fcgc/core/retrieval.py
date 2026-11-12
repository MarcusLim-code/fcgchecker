"""Compatibility import for :mod:`fcgc.retrieval.search_pipeline`; edit that module instead."""

import sys

import fcgc.retrieval.search_pipeline as _implementation

sys.modules[__name__] = _implementation
