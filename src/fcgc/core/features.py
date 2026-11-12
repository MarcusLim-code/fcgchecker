"""Compatibility import for :mod:`fcgc.checking.feature_extractor`; edit that module instead."""

import sys

import fcgc.checking.feature_extractor as _implementation

sys.modules[__name__] = _implementation
