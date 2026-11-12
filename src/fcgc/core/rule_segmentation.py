"""Compatibility import for :mod:`fcgc.checking.rule_extractor`; edit that module instead."""

import sys

import fcgc.checking.rule_extractor as _implementation

sys.modules[__name__] = _implementation
