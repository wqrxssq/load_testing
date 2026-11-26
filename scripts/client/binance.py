import argparse
import asyncio
import json
import sys

import websockets

STREAMS = {
    "trades": ("market", "aggTrade"),
    "book_tickers": ("public", "bookTicker"),
    "incrementals": ("public", "depth@100ms"),
}

BASE_URL = "wss://fstream.binance.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Subscribe to a Binance USD-M stream (combined stream via URL)."
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=sorted(STREAMS),
        help="data type: trades, book_tickers, or incrementals",
    )
    parser.add_argument(
        "--security",
        required=True,
        help="instrument as Binance writes it, for example BTCUSDT",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="stop after N messages; 0 runs until interrupted",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="print each JSON message on one line",
    )
    args = parser.parse_args()
    if args.count < 0:
        parser.error("--count must be >= 0")
    return args


def build_url(data_type: str, security: str) -> str:
    symbol = security.strip().lower()
    if not symbol or not all(char.isalnum() or char == "_" for char in symbol):
        raise SystemExit(f"Binance instrument looks like BTCUSDT, got {security!r}")
    route, stream = STREAMS[data_type]
    return f"{BASE_URL}/{route}/stream?streams={symbol}@{stream}"


def snapshot_hint(security: str) -> str:
    symbol = security.strip().upper()
    return (
        "This Binance stream sends deltas only. Order book snapshot:\n"
        f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=1000"
    )


async def listen(url: str, count: int, compact: bool) -> None:
    indent = None if compact else 2
    received = 0
    async with websockets.connect(url, open_timeout=15, ping_interval=20, ping_timeout=20) as ws:
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode()
            message = json.loads(raw)
            print(json.dumps(message, indent=indent, ensure_ascii=False), flush=True)
            received += 1
            if count and received >= count:
                return


def main() -> None:
    args = parse_args()
    url = build_url(args.type, args.security)
    print(f"connecting {url}", file=sys.stderr)
    if args.type == "incrementals":
        print(snapshot_hint(args.security), file=sys.stderr)
    try:
        asyncio.run(listen(url, args.count, args.compact))
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)


main()
