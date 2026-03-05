"""
Register M-Pesa C2B callback URLs in Daraja (sandbox/production).

This script:
1) Reads MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET from .env
2) Generates MPESA_WEBHOOK_TOKEN if missing/blank (and writes it back to .env)
3) Obtains OAuth access token from Daraja
4) Calls C2B Register URL endpoint with ValidationURL/ConfirmationURL

Usage:
  uv run python scripts/mpesa_register_c2b_urls.py \\
    --public-base-url https://xxxx.ngrok-free.app \\
    --short-code 600000
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

import httpx


ENV_BASE_URLS: dict[str, str] = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


def _read_env_file(path: Path) -> tuple[list[str], dict[str, str]]:
    if not path.exists():
        return [], {}
    lines = path.read_text(encoding="utf-8").splitlines(keepends=False)
    env: dict[str, str] = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()
    return lines, env


def _upsert_env_var(lines: list[str], key: str, value: str) -> list[str]:
    out: list[str] = []
    found = False
    for ln in lines:
        if ln.strip().startswith("#") or "=" not in ln:
            out.append(ln)
            continue
        k, _v = ln.split("=", 1)
        if k.strip() == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(f"{key}={value}")
    return out


def _ensure_webhook_token(env_path: Path) -> str:
    lines, env = _read_env_file(env_path)
    token = (env.get("MPESA_WEBHOOK_TOKEN") or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    updated = _upsert_env_var(lines, "MPESA_WEBHOOK_TOKEN", token)
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return token


def _get_oauth_access_token(
    *,
    base_url: str,
    consumer_key: str,
    consumer_secret: str,
    timeout_s: float = 30.0,
) -> str:
    url = f"{base_url}/oauth/v1/generate"
    params = {"grant_type": "client_credentials"}
    resp = httpx.get(
        url,
        params=params,
        auth=(consumer_key, consumer_secret),
        timeout=timeout_s,
    )
    resp.raise_for_status()
    data = resp.json()
    token = (data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError(f"Daraja OAuth response missing access_token: {data!r}")
    return token


def _register_c2b_urls(
    *,
    base_url: str,
    access_token: str,
    short_code: str,
    validation_url: str,
    confirmation_url: str,
    response_type: str = "Completed",
    timeout_s: float = 30.0,
) -> dict:
    # Daraja 3.0 docs: https://sandbox.safaricom.co.ke/mpesa/c2b/v2/registerurl
    url = f"{base_url}/mpesa/c2b/v2/registerurl"
    payload = {
        "ShortCode": short_code,
        "ResponseType": response_type,
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"

    p = argparse.ArgumentParser(description="Register Daraja C2B callback URLs.")
    p.add_argument(
        "--public-base-url",
        required=True,
        help=(
            "Public HTTPS base URL for your backend (ngrok/cloudflared), "
            "e.g. https://xxxx.ngrok-free.app"
        ),
    )
    p.add_argument(
        "--short-code",
        default="",
        help="Paybill/Till shortcode (overrides MPESA_SHORT_CODE from .env).",
    )
    p.add_argument(
        "--env",
        dest="mpesa_env",
        default="",
        help="sandbox or production (overrides MPESA_ENVIRONMENT from .env).",
    )
    p.add_argument(
        "--response-type",
        default="Completed",
        help="Daraja ResponseType for Register URL (usually Completed).",
    )
    p.add_argument(
        "--timeout-s",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds for Daraja calls (default: 60).",
    )
    args = p.parse_args()

    public_base_url = args.public_base_url.rstrip("/")
    if not public_base_url.startswith("https://"):
        raise SystemExit("--public-base-url must be https://")

    lines, env = _read_env_file(env_path)
    consumer_key = (env.get("MPESA_CONSUMER_KEY") or "").strip()
    consumer_secret = (env.get("MPESA_CONSUMER_SECRET") or "").strip()
    if not consumer_key or not consumer_secret:
        raise SystemExit("Missing MPESA_CONSUMER_KEY/MPESA_CONSUMER_SECRET in .env")

    mpesa_env = (
        args.mpesa_env or env.get("MPESA_ENVIRONMENT") or "sandbox"
    ).strip().lower()
    if mpesa_env not in ENV_BASE_URLS:
        raise SystemExit(f"Invalid environment {mpesa_env!r}. Use: sandbox|production")

    base_url = ENV_BASE_URLS[mpesa_env]

    short_code = (args.short_code or env.get("MPESA_SHORT_CODE") or "").strip()
    if not short_code:
        raise SystemExit(
            "Missing shortcode. Provide --short-code or set MPESA_SHORT_CODE in .env"
        )

    webhook_token = _ensure_webhook_token(env_path)

    validation_url = f"{public_base_url}/api/v1/c2b/validation/{webhook_token}"
    confirmation_url = f"{public_base_url}/api/v1/c2b/confirmation/{webhook_token}"

    print(f"Daraja env: {mpesa_env} ({base_url})")
    print(f"ShortCode: {short_code}")
    print(f"ValidationURL: {validation_url}")
    print(f"ConfirmationURL: {confirmation_url}")

    access_token = _get_oauth_access_token(
        base_url=base_url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        timeout_s=args.timeout_s,
    )
    print("OAuth token: OK")

    result = _register_c2b_urls(
        base_url=base_url,
        access_token=access_token,
        short_code=short_code,
        validation_url=validation_url,
        confirmation_url=confirmation_url,
        response_type=args.response_type,
        timeout_s=args.timeout_s,
    )
    print("Register URL response:")
    print(result)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as exc:
        resp = exc.response
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = resp.text
        print(f"HTTP {resp.status_code} calling {resp.request.url}", file=sys.stderr)
        print(body, file=sys.stderr)
        raise
