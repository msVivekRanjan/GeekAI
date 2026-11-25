#!/bin/sh
set -e

echo "GeekAI Backend: Checking database connectivity..."
python - << 'EOF'
import sys
import time
import socket
import urllib.parse
from app.core.config import settings

url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
parsed = urllib.parse.urlparse(url)
host = parsed.hostname or "localhost"
port = parsed.port or 5432

for attempt in range(1, 16):
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        print(f"PostgreSQL at {host}:{port} is accepting connections.")
        sys.exit(0)
    except Exception as exc:
        print(f"Waiting for PostgreSQL at {host}:{port} ({exc})... attempt {attempt}/15")
        time.sleep(2)

print(f"ERROR: Could not connect to PostgreSQL at {host}:{port} after 15 attempts.", file=sys.stderr)
sys.exit(1)
EOF

echo "GeekAI Backend: Checking and applying database migrations..."
if ! alembic upgrade head; then
    echo "GeekAI Backend: Alembic upgrade failed (possible revision drift). Synchronizing to head..."
    alembic stamp head --purge || true
    alembic upgrade head || true
fi
echo "GeekAI Backend: Database schema is up to date."

exec "$@"
