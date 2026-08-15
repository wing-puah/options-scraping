"""
IBKR Flex Web Service — thin client.

Transport and parsing only, mirroring the role `lib.barchart` plays for
Barchart: no trading/business logic lives here. Talks to the token-authenticated
Flex Web Service; there is no gateway, no port and no browser session involved.

The Client Portal Web API client that used to live here (`client.py`,
`endpoints.py`, `contracts.py`) was removed on 2026-08-15 along with the journal
transport that was its only caller — see `scripts/journal/pull.py`.
"""
from __future__ import annotations

from lib.ibkr.flex import FlexClient, FlexError, positions_query_id_from_env

__all__ = [
    "FlexClient",
    "FlexError",
    "positions_query_id_from_env",
]
