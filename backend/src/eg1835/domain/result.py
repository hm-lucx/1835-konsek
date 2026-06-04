"""Generic two-track Result type used throughout the action layer.

Ok[T]  -- successful computation carrying a value of type T.
Err[E] -- failed computation carrying an error of type E.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):  # noqa: UP046
    """Successful result."""

    value: T


@dataclass(frozen=True)
class Err(Generic[E]):  # noqa: UP046
    """Error result."""

    error: E
