"""Compatibility import for :mod:`fcgc.checking.compliance_checker`; edit that module instead."""

import sys

import fcgc.checking.compliance_checker as _implementation

sys.modules[__name__] = _implementation
