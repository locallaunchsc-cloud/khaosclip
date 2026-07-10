from khaosclip.events import ClipEvent, EventBus


def test_publish_and_consume():
    bus = EventBus()
    assert bus.publish(ClipEvent(source="voice", detail="clip that"))
    ev = bus.next(timeout=0.1)
    assert ev.source == "voice"
    assert ev.detail == "clip that"


def test_queue_full_does_not_block():
    bus = EventBus(maxsize=1)
    assert bus.publish(ClipEvent(source="voice"))
    assert bus.publish(ClipEvent(source="voice")) is False  # dropped, not blocked


def test_empty_queue_returns_none():
    bus = EventBus()
    assert bus.next(timeout=0.05) is None
