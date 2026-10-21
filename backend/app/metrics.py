from collections import Counter

counters: Counter = Counter()

def incr(name, amount= 1):
    counters[name] += amount