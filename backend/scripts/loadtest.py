"""DEV ONLY: load test. CLIENTS websocket clients join one channel while a sender posts
MESSAGES messages over HTTP at RATE per second; every client records when each one arrives.

Usage, from backend/ after `source scripts/compose_env.sh`:
    python -m scripts.loadtest CLIENTS MESSAGES [RATE]
"""
import asyncio
import contextlib
import os
import resource
import statistics
import sys
import time
import uuid
from collections import Counter

import aiohttp
import socketio


CONNECT_TIMEOUT = float(os.environ.get("LT_CONNECT_TIMEOUT", "30"))
HOLD = float(os.environ.get("LT_HOLD", "8"))
attempted = 0

if len(sys.argv) < 3:
    sys.exit("usage: python -m scripts.loadtest CLIENTS MESSAGES [RATE]")
CLIENTS, MESSAGES = int(sys.argv[1]), int(sys.argv[2])
RATE = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
BASE, TOKEN = os.environ["BASE"], os.environ["OWNER"]
WS, CH = os.environ["WS"], os.environ["CH"]

PREFIX = f"lt-{uuid.uuid4().hex[:6]}-"
sent_at = {}         # message index -> perf_counter() just before its POST
latencies_ms = []    # one entry per (message, client) delivery
received = 0


async def on_message(data):
    global received
    body = data["message"]["body"]
    if body.startswith(PREFIX):
        started = sent_at.get(int(body[len(PREFIX):]))
        if started is not None:
            latencies_ms.append((time.perf_counter() - started) * 1000)
            received += 1


async def connect_and_join(sio):
    await sio.connect(BASE, auth={"token": TOKEN}, transports=["websocket"], wait_timeout=20)
    ack = await sio.call("channel.join", {"workspace_id": WS, "channel_id": CH}, timeout=20)
    if not ack.get("ok"):
        raise RuntimeError(f"join refused: {ack}")


async def open_client(gate, failures, connect_ms):
    global attempted
    async with gate:
        sio = socketio.AsyncClient(reconnection=False)
        sio.on("message.sent", on_message)
        began = time.perf_counter()
        try:
            await asyncio.wait_for(connect_and_join(sio), timeout=CONNECT_TIMEOUT)
        except Exception as exc:
            failures[type(exc).__name__] += 1
            with contextlib.suppress(Exception):
                await asyncio.wait_for(sio.disconnect(), timeout=5)
            sio = None
        else:
            connect_ms.append((time.perf_counter() - began) * 1000)
        attempted += 1
        if attempted % 25 == 0 or attempted == CLIENTS:
            print(f"  {attempted}/{CLIENTS} attempted, {sum(failures.values())} failed", flush=True)
        return sio


async def send_all(session, statuses, http_ms):
    accepted = []
    headers = {"Authorization": f"Bearer {TOKEN}"}
    interval = 1.0 / RATE
    due = time.perf_counter()
    for i in range(MESSAGES):
        sent_at[i] = time.perf_counter()
        try:
            async with session.post(
                f"{BASE}/workspaces/{WS}/channels/{CH}/messages",
                json={"body": f"{PREFIX}{i}"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                await response.read()
                statuses[response.status] += 1
                http_ms.append((time.perf_counter() - sent_at[i]) * 1000)
                if response.status == 201:
                    accepted.append(i)
        except Exception as exc:
            statuses[type(exc).__name__] += 1
        due += interval
        await asyncio.sleep(max(0.0, due - time.perf_counter()))
    return accepted


def pct(values, p):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]


async def preflight():
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{BASE}/workspaces/{WS}", headers={"Authorization": f"Bearer {TOKEN}"}) as r:
            if r.status != 200:
                sys.exit(f"preflight failed: GET /workspaces/{WS} gave {r.status}. "
                         "Expired token? Run `source scripts/compose_env.sh` again.")


async def main():
    await preflight()
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    if CLIENTS + 50 > soft:
        print(f"warning: open-file limit is {soft}; run `ulimit -n 8192` first")

    failures, connect_ms = Counter(), []
    gate = asyncio.Semaphore(25)  # open connections in small batches, not all at once
    began = time.perf_counter()
    opened = await asyncio.gather(*(open_client(gate, failures, connect_ms) for _ in range(CLIENTS)))
    clients = [c for c in opened if c is not None]
    print(f"connected {len(clients)}/{CLIENTS} in {time.perf_counter() - began:.1f}s; "
          f"failures: {dict(failures) or 'none'}")
    print(f"holding {HOLD:.0f}s: run `sockets` and `docker stats --no-stream` now", flush=True)
    await asyncio.sleep(HOLD)

    print("sending... (take a `docker stats --no-stream` now)")
    statuses, http_ms = Counter(), []
    async with aiohttp.ClientSession() as session:
        accepted = await send_all(session, statuses, http_ms)

    expected = len(clients) * len(accepted)
    deadline = time.perf_counter() + 10
    while received < expected and time.perf_counter() < deadline:
        await asyncio.sleep(0.2)

    ratio = received / expected * 100 if expected else float("nan")
    print(f"\nclients connected : {len(clients)}/{CLIENTS}")
    print(f"connect+join ms   : p50 {pct(connect_ms, 50):.0f}   p95 {pct(connect_ms, 95):.0f}")
    print(f"POST status codes : {dict(statuses)}")
    print(f"POST ms           : p50 {pct(http_ms, 50):.0f}   p95 {pct(http_ms, 95):.0f}")
    print(f"deliveries        : {received}/{expected} ({ratio:.1f}%)")
    print(f"delivery latency  : p50 {pct(latencies_ms, 50):.0f}   p95 {pct(latencies_ms, 95):.0f}   "
          f"p99 {pct(latencies_ms, 99):.0f}   max {max(latencies_ms, default=float('nan')):.0f} ms")
    if latencies_ms:
        print(f"mean latency      : {statistics.fmean(latencies_ms):.0f} ms")

    await asyncio.gather(*(c.disconnect() for c in clients), return_exceptions=True)


asyncio.run(main())