"""Compatibility import for :mod:`fcgc.checking.document_normalizer`; edit that module instead."""

import sys

import fcgc.checking.document_normalizer as _implementation

sys.modules[__name__] = _implementation
