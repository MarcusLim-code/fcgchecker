"""Compatibility import for :mod:`fcgc.retrieval.atlassian`; edit that module instead."""

import sys

import fcgc.retrieval.atlassian as _implementation

sys.modules[__name__] = _implementation
