"""
IBKR Flex Web Service — thin client.

Transport and parsing only, mirroring the role `lib.barchart` plays for
Barchart: no trading/business logic lives here. Talks to the token-authenticated
Flex Web Service; there is no gateway, no port and no browser session involved.

The Client Portal Web API client that used to live here (`client.py`,
`endpoints.py`, `contracts.py`) was removed on 2026-08-15 along with the journal
transport that was its only caller — see `scripts/journal/pull.py`.

No re-exports live here on purpose: every consumer imports `lib.ibkr.flex`
directly, so a convenience alias would be a second name for one class with
nothing keeping the two in step.
"""
