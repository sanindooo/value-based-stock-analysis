"""Patch the database engine before any app module tries to import asyncpg."""

import sys
from unittest.mock import AsyncMock, MagicMock

# Create a fake asyncpg module so SQLAlchemy's create_async_engine
# can proceed without the real C-extension driver.
if "asyncpg" not in sys.modules:
    fake_asyncpg = MagicMock()
    fake_asyncpg.connect = AsyncMock()
    sys.modules["asyncpg"] = fake_asyncpg
    sys.modules["asyncpg.pgproto"] = MagicMock()
    sys.modules["asyncpg.pgproto.pgproto"] = MagicMock()
    sys.modules["asyncpg.protocol"] = MagicMock()
    sys.modules["asyncpg.protocol.protocol"] = MagicMock()
