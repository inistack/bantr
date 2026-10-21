"""DEV ONLY: compare channel-open latency with the message cache on and off.

Usage: python -m scripts.bench_history [REQUESTS_PER_SERVER]
Needs OWNER, ALPHA and CH in the environment (source scripts/dev_env.sh), a server
with the cache on (BANTR_URL_ON, default http://127.0.0.1:5000) and one started with
MESSAGE_CACHE_ENABLED=0 (BANTR_URL_OFF, default http://127.0.0.1:5002).
"""
import os
import statistics
import sys
import time

import requests

TOTAL = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ROUNDS = 5
token, ws, ch = os.environ["OWNER"], os.environ["ALPHA"], os.environ["CH"]
targets = {
    "cache on": os.environ.get("BANTR_URL_ON", "http://127.0.0.1:5000"),
    "cache off": os.environ.get("BANTR_URL_OFF", "http://127.0.0.1:5002"),
}
session = requests.Session()
session.headers["Authorization"] = f"Bearer {token}"


def get(base):
    r = session.get(f"{base}/workspaces/{ws}/channels/{ch}/messages", timeout=10)
    r.raise_for_status()
    return r.json()


def timed(base, n):
    out = []
    for _ in range(n):
        start = time.perf_counter()
        get(base)
        out.append((time.perf_counter() - start) * 1000)
    return out


payloads = {name: get(url) for name, url in targets.items()}
if payloads["cache on"] != payloads["cache off"]:
    sys.exit("the two servers returned different data; not comparing")
print(f"both servers return the same {len(payloads['cache on'])} messages")

for url in targets.values():  # warm-up
    timed(url, 20)

samples = {name: [] for name in targets}
per_round = max(1, TOTAL // ROUNDS)
for _ in range(ROUNDS):  # alternate, so drift on the machine affects both equally
    for name, url in targets.items():
        samples[name] += timed(url, per_round)

print(f"\n{'':10} {'n':>5} {'min':>7} {'p50':>7} {'p95':>7} {'mean':>7}   (ms)")
p50 = {}
for name, s in samples.items():
    s.sort()
    p50[name] = s[len(s) // 2]
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    print(f"{name:10} {len(s):>5} {s[0]:7.1f} {p50[name]:7.1f} {p95:7.1f} {statistics.fmean(s):7.1f}")
print(f"\np50 ratio (off / on): {p50['cache off'] / p50['cache on']:.2f}x")