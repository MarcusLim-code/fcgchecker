"""Compatibility import for :mod:`fcgc.integrations.mock_checker`; edit that module instead."""

import sys

import fcgc.integrations.mock_checker as _implementation

sys.modules[__name__] = _implementation
