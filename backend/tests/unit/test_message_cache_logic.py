import fakeredis
import pytest

from app.services import message_cache as c


def msg(seq):
    return {"id": f"id{seq}", "seq": seq, "body": f"m{seq}", "created_at": "t",
            "user": {"id": "u", "name": "n", "avatar_url": None}}


def window(first, last):
    return [msg(s) for s in range(first, last + 1)]


@pytest.fixture
def r():
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


def test_an_empty_channel_reads_as_an_empty_window(r):
    assert c.read(r, "w", "c", last_seq=0) == []


def test_no_cache_yet_is_a_miss(r):
    assert c.read(r, "w", "c", last_seq=5) is None


def test_fill_then_read_returns_messages_oldest_first(r):
    c.fill(r, "w", "c", window(1, 5))
    assert c.read(r, "w", "c", last_seq=5) == window(1, 5)


def test_a_long_channel_is_served_as_its_newest_50(r):
    c.fill(r, "w", "c", window(71, 120))
    got = c.read(r, "w", "c", last_seq=120)
    assert [m["seq"] for m in got] == list(range(71, 121))


def test_a_stale_cache_is_a_miss(r):
    c.fill(r, "w", "c", window(1, 10))
    assert c.read(r, "w", "c", last_seq=11) is None


def test_an_incomplete_cache_is_a_miss(r):
    c.fill(r, "w", "c", window(10, 10)) 
    assert c.read(r, "w", "c", last_seq=10) is None


def test_a_cache_with_a_hole_is_a_miss(r):
    c.fill(r, "w", "c", [msg(1), msg(2), msg(4), msg(5)])
    assert c.read(r, "w", "c", last_seq=5) is None


def test_fill_replaces_previous_contents(r):
    c.fill(r, "w", "c", window(61, 110))
    c.fill(r, "w", "c", window(71, 120))
    got = c.read(r, "w", "c", last_seq=120)
    assert [m["seq"] for m in got] == list(range(71, 121))
    assert r.zcard(c._key("w", "c")) == 50  


def test_cache_is_separate_per_workspace_and_channel(r):
    c.fill(r, "w1", "c", window(1, 3))
    assert c.read(r, "w2", "c", last_seq=3) is None
    assert c.read(r, "w1", "other", last_seq=3) is None


def test_damaged_contents_raise_so_the_caller_can_treat_them_as_a_miss(r):
    r.zadd(c._key("w", "c"), {"this is not json": 1})
    with pytest.raises(ValueError):
        c.read(r, "w", "c", last_seq=1)


def test_append_to_a_warm_cache_keeps_it_valid(r):
    c.fill(r, "w", "c", window(1, 5))
    assert c.append(r, "w", "c", msg(6)) is True
    assert c.read(r, "w", "c", last_seq=6) == window(1, 6)


def test_append_trims_to_the_newest_50(r):
    c.fill(r, "w", "c", window(51, 100))
    c.append(r, "w", "c", msg(101))
    got = c.read(r, "w", "c", last_seq=101)
    assert [m["seq"] for m in got] == list(range(52, 102))
    assert r.zcard(c._key("w", "c")) == 50


def test_append_to_a_cold_cache_creates_nothing(r):
    assert c.append(r, "w", "c", msg(1)) is False
    assert r.exists(c._key("w", "c")) == 0


def test_appending_the_same_message_twice_does_not_duplicate_it(r):
    c.fill(r, "w", "c", window(1, 5))
    c.append(r, "w", "c", msg(6))
    c.append(r, "w", "c", msg(6))
    assert r.zcard(c._key("w", "c")) == 6
    assert c.read(r, "w", "c", last_seq=6) == window(1, 6)


def test_out_of_order_appends_end_up_ordered_and_a_hole_is_never_served(r):
    c.fill(r, "w", "c", window(1, 5))
    c.append(r, "w", "c", msg(7))
    assert c.read(r, "w", "c", last_seq=7) is None  # seq 6 is still missing
    c.append(r, "w", "c", msg(6))
    assert c.read(r, "w", "c", last_seq=7) == window(1, 7)


def test_append_replaces_an_entry_with_the_same_seq(r):
    c.fill(r, "w", "c", window(1, 5))
    c.append(r, "w", "c", {**msg(5), "body": "edited"})
    got = c.read(r, "w", "c", last_seq=5)
    assert got[-1]["body"] == "edited"
    assert r.zcard(c._key("w", "c")) == 5