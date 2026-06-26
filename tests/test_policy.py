from matrixd.core.policy import Event, Policy, RoomPolicy


def make_event(
    event_id: str,
    sender: str,
    *,
    body: str = "hello",
    relates_to: dict | None = None,
) -> Event:
    content = {"msgtype": "m.text", "body": body}
    if relates_to:
        content["m.relates_to"] = relates_to
    return Event.from_sync(
        "!room:example.com",
        {
            "type": "m.room.message",
            "event_id": event_id,
            "sender": sender,
            "origin_server_ts": 1,
            "content": content,
        },
    )


def test_important_delivers_reply_to_cached_own_message() -> None:
    policy = Policy(default_policy=RoomPolicy.IMPORTANT)
    own_event = make_event("$own", "@bot:example.com")
    reply = make_event(
        "$reply",
        "@alice:example.com",
        relates_to={"m.in_reply_to": {"event_id": "$own"}},
    )

    assert own_event is not None
    assert reply is not None
    assert not policy.should_deliver(own_event, "@bot:example.com")
    assert policy.should_deliver(reply, "@bot:example.com")


def test_important_ignores_reply_to_other_user() -> None:
    policy = Policy(default_policy=RoomPolicy.IMPORTANT)
    other_event = make_event("$other", "@bob:example.com")
    reply = make_event(
        "$reply",
        "@alice:example.com",
        relates_to={"m.in_reply_to": {"event_id": "$other"}},
    )

    assert other_event is not None
    assert reply is not None
    assert not policy.should_deliver(other_event, "@bot:example.com")
    assert not policy.should_deliver(reply, "@bot:example.com")


def test_mention_only_ignores_reply_to_cached_own_message() -> None:
    policy = Policy(default_policy=RoomPolicy.MENTION_ONLY)
    own_event = make_event("$own", "@bot:example.com")
    reply = make_event(
        "$reply",
        "@alice:example.com",
        relates_to={"m.in_reply_to": {"event_id": "$own"}},
    )

    assert own_event is not None
    assert reply is not None
    assert not policy.should_deliver(own_event, "@bot:example.com")
    assert not policy.should_deliver(reply, "@bot:example.com")


def test_event_cache_respects_max_cached_events() -> None:
    policy = Policy(default_policy=RoomPolicy.ALL, max_cached_events=2)

    for index in range(3):
        event = make_event(f"${index}", "@alice:example.com")
        assert event is not None
        assert policy.should_deliver(event, "@bot:example.com")

    assert "$0" not in policy._event_senders
    assert policy._event_senders == {"$1": "@alice:example.com", "$2": "@alice:example.com"}
