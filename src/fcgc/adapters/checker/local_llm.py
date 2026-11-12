"""Compatibility import for :mod:`fcgc.integrations.ollama_checker`; edit that module instead."""

import sys

import fcgc.integrations.ollama_checker as _implementation

sys.modules[__name__] = _implementation
