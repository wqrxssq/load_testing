import argparse
import asyncio
import contextlib
import json
import sys

import websockets

# Logical type -> OKX channel.
CHANNELS = {
    "trades": "trades",
    "book_tickers": "bbo-tbt",
    "incrementals": "books",
}

URL = "wss://ws.okx.com/ws/v5/public"
PING_INTERVAL_SEC = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe to a public OKX channel.")
    parser.add_argument(
        "--type",
        required=True,
        choices=sorted(CHANNELS),
        help="data type: trades, book_tickers, or incrementals",
    )
    parser.add_argument(
        "--security",
        required=True,
        help="instrument as OKX writes it, for example BTC-USDT-SWAP",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="stop after N market messages; 0 runs until interrupted",
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


def check_security(security: str) -> str:
    instrument = security.strip()
    if not instrument or not all(char.isalnum() or char in "-_" for char in instrument):
        raise SystemExit(f"OKX instrument looks like BTC-USDT-SWAP, got {security!r}")
    return instrument


async def heartbeat(ws) -> None:
    # OKX closes the socket after 30s of silence. A text ping keeps it open.
    while True:
        await asyncio.sleep(PING_INTERVAL_SEC)
        await ws.send("ping")


async def listen(channel: str, instrument: str, count: int, compact: bool) -> None:
    indent = None if compact else 2
    subscribe = {
        "id": "1",
        "op": "subscribe",
        "args": [{"channel": channel, "instId": instrument}],
    }
    received = 0
    async with websockets.connect(
        URL,
        open_timeout=15,
        ping_interval=20,
        ping_timeout=20,
        max_size=8_000_000,
    ) as ws:
        await ws.send(json.dumps(subscribe))
        pinger = asyncio.create_task(heartbeat(ws))
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    raw = raw.decode()
                if raw == "pong":
                    continue
                if raw == "ping":
                    await ws.send("pong")
                    continue
                message = json.loads(raw)
                event = message.get("event")
                if event == "error":
                    print(json.dumps(message, ensure_ascii=False), file=sys.stderr)
                    raise SystemExit(1)
                if event in {"subscribe", "unsubscribe"}:
                    print(json.dumps(message, ensure_ascii=False), file=sys.stderr)
                    continue
                print(json.dumps(message, indent=indent, ensure_ascii=False), flush=True)
                received += 1
                if count and received >= count:
                    return
        finally:
            pinger.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pinger


def main() -> None:
    args = parse_args()
    instrument = check_security(args.security)
    channel = CHANNELS[args.type]
    print(f"connecting {URL}  channel={channel}  instId={instrument}", file=sys.stderr)
    try:
        asyncio.run(listen(channel, instrument, args.count, args.compact))
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)


main()
