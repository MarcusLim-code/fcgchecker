"""Compatibility import for :mod:`fcgc.retrieval.mcp_bridge`; edit that module instead."""

import sys

import fcgc.retrieval.mcp_bridge as _implementation

sys.modules[__name__] = _implementation
