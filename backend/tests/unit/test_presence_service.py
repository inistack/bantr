import fakeredis
import pytest

from app.services import presence_service as p

TTL = 30


@pytest.fixture
def r():
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


def test_first_connection_brings_user_online_in_each_workspace(r):
    assert p.add_connection(r, ["w1", "w2"], "alice", "s1", 1000, TTL) == ["w1", "w2"]
    assert p.online_user_ids(r, "w1", 1000, TTL) == ["alice"]
    assert p.online_user_ids(r, "w2", 1000, TTL) == ["alice"]


def test_second_connection_of_the_same_user_is_not_a_new_transition(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    assert p.add_connection(r, ["w1"], "alice", "s2", 1001, TTL) == []


def test_user_goes_offline_only_when_the_last_connection_closes(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    p.add_connection(r, ["w1"], "alice", "s2", 1000, TTL)
    assert p.remove_connection(r, ["w1"], "alice", "s1", 1005, TTL) == []
    assert p.online_user_ids(r, "w1", 1005, TTL) == ["alice"]
    assert p.remove_connection(r, ["w1"], "alice", "s2", 1006, TTL) == ["w1"]
    assert p.online_user_ids(r, "w1", 1006, TTL) == []


def test_removing_an_unknown_connection_reports_nothing(r):
    assert p.remove_connection(r, ["w1"], "alice", "ghost", 1000, TTL) == []


def test_presence_is_scoped_per_workspace(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    p.add_connection(r, ["w2"], "bob", "s2", 1000, TTL)
    assert p.online_user_ids(r, "w1", 1000, TTL) == ["alice"]
    assert p.online_user_ids(r, "w2", 1000, TTL) == ["bob"]


def test_connections_expire_when_not_refreshed(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    assert p.online_user_ids(r, "w1", 1000 + TTL - 1, TTL) == ["alice"]
    assert p.online_user_ids(r, "w1", 1000 + TTL + 1, TTL) == []


def test_heartbeat_keeps_a_connection_alive(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    p.heartbeat(r, [(["w1"], "alice", "s1")], now=1025)
    assert p.online_user_ids(r, "w1", 1050, TTL) == ["alice"]


def test_reaper_removes_dead_connections_and_reports_each_user_once(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)  
    assert p.reap_stale(r, "w1", now=1100, ttl=TTL) == ["alice"]
    assert p.reap_stale(r, "w1", now=1100, ttl=TTL) == []  


def test_reaper_does_not_report_a_user_who_still_has_a_live_connection(r):
    p.add_connection(r, ["w1"], "alice", "dead", 1000, TTL)
    p.add_connection(r, ["w1"], "alice", "alive", 1090, TTL)
    assert p.reap_stale(r, "w1", now=1100, ttl=TTL) == []
    assert p.online_user_ids(r, "w1", 1100, TTL) == ["alice"]


def test_heartbeat_reports_entries_that_had_been_reaped(r):
    p.add_connection(r, ["w1"], "alice", "s1", 1000, TTL)
    p.reap_stale(r, "w1", now=1100, ttl=TTL)
    assert p.heartbeat(r, [(["w1"], "alice", "s1")], now=1101) == [("w1", "alice")]
    assert p.heartbeat(r, [(["w1"], "alice", "s1")], now=1102) == []  