"""Typed adapter failures (in addition to the HTTP-level ones in ``http.py``)."""

from __future__ import annotations


class AdapterError(Exception):
    """The adapter could not interpret the source (layout or contract changed)."""

    error_type = "adapter_error"


class ParseError(AdapterError):
    error_type = "parse_error"


class StoreContextError(AdapterError):
    """The requested store/region could not be applied, so prices would be wrong."""

    error_type = "store_context_error"
