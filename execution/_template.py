#!/usr/bin/env python3
"""[DESCRIPTION — one line explaining what this script does].

Usage:
    python execution/[script_name].py --input .tmp/input.json --output .tmp/output.json
    python execution/[script_name].py --input .tmp/input.json --output .tmp/output.json --mock
    python execution/[script_name].py --input .tmp/input.json --output .tmp/output.json --dry-run
"""

import argparse
import ipaddress
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB

# ── Helpers ────────────────────────────────────────────────────────
# Keep or remove each helper based on what this script needs.
# At minimum, keep _error_exit and _safe_path — they're required by
# the execution script standards.


def _error_exit(code: str, message: str) -> None:
    """Emit structured JSON error to stdout and exit non-zero."""
    print(json.dumps({"status": "error", "error_code": code, "message": message}))
    sys.exit(1)


def _safe_path(path_str: str) -> Path:
    """Validate that a path resolves under PROJECT_ROOT/.tmp/."""
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    resolved = Path(path_str).resolve()
    if not (str(resolved).startswith(str(allowed) + os.sep) or resolved == allowed):
        _error_exit("path_violation", f"Path must be under {allowed} — got {resolved}")
    return resolved


# Remove if this script doesn't make HTTP requests.
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def _validate_url(url: str) -> str:
    """Block private-network and non-HTTP URLs (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        _error_exit("invalid_url", f"Only http/https allowed — got {parsed.scheme}://")
    hostname = parsed.hostname
    if not hostname:
        _error_exit("invalid_url", f"No hostname in URL: {url}")
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                _error_exit("ssrf_blocked", f"Private network URL blocked: {url}")
    except ValueError:
        pass  # hostname is a domain name — blocks obvious IP-based SSRF but not DNS rebinding
    return url


# Remove if this script doesn't log PII (emails, phone numbers).
def _redact_pii(email: str) -> str:
    """Mask email for logging: j***@example.com."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}" if local else f"***@{domain}"


# Remove if this script doesn't write files with sensitive data.
def _atomic_write(path: Path, content: str, permissions: int = 0o600) -> None:
    """Write atomically via temp file + os.replace(). Sets 0o600 by default."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp_path, permissions)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# Remove if this script doesn't write to Google Sheets.
def _sanitize_for_sheets(value: str) -> str:
    """Prevent formula injection — prefix dangerous first characters."""
    if isinstance(value, str) and value.lstrip() and value.lstrip()[0] in "=+-@":
        return "'" + value
    return value


# ── Main ───────────────────────────────────────────────────────────


def run(args: argparse.Namespace) -> dict:
    """Core logic. Returns a result dict for structured output."""
    if args.mock:
        log.info("Mock mode — no external calls")
        return {"status": "success", "mock": True, "count": 0}

    if args.dry_run:
        log.info("Dry run — showing what would happen")
        return {"status": "success", "dry_run": True, "count": 0}

    # TODO: implement real logic here
    return {"status": "success", "count": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input file path (must be under .tmp/)")
    parser.add_argument("--output", required=True, help="Output file path (must be under .tmp/)")
    parser.add_argument("--mock", action="store_true", help="Return mock data without external calls")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would happen without side effects")
    args = parser.parse_args()

    input_path = _safe_path(args.input)
    output_path = _safe_path(args.output)

    if not input_path.exists():
        _error_exit("file_not_found", f"Input file not found: {input_path}")

    result = run(args)
    _atomic_write(output_path, json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
