"""Compatibility import for :mod:`fcgc.retrieval.replay_retriever`; edit that module instead."""

import sys

import fcgc.retrieval.replay_retriever as _implementation

sys.modules[__name__] = _implementation
