"""Compatibility import for :mod:`fcgc.retrieval.local_retriever`; edit that module instead."""

import sys

import fcgc.retrieval.local_retriever as _implementation

sys.modules[__name__] = _implementation
