#!/usr/bin/env python3
"""Resolve matter-private storage paths via SECOND_REVIEW_PRIVATE_DIR."""

from __future__ import annotations

import os

ENV_NAME = "SECOND_REVIEW_PRIVATE_DIR"


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def private_dir() -> str:
    configured = os.environ.get(ENV_NAME)
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    return repo_root()


def input_dir() -> str:
    return os.path.join(private_dir(), "input")


def output_dir() -> str:
    return os.path.join(private_dir(), "output")
