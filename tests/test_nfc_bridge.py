import os
import tempfile

import pytest

# nfc_bridge legt beim Import einen Log-Handler an - nicht ins echte instance/ schreiben.
os.environ.setdefault("NFC_LOG_DIR", tempfile.mkdtemp(prefix="nfc-bridge-test-"))

nfc_bridge = pytest.importorskip("nfc_bridge")
CardPresence = nfc_bridge.CardPresence


def test_card_is_reported_once_while_it_stays_on_the_reader():
    presence = CardPresence(removal_grace=1.0)
    assert presence.seen("04AA", 0.0) is True
    assert presence.seen("04AA", 0.5) is False
    assert presence.seen("04AA", 10.0) is False


def test_short_dropout_does_not_trigger_a_new_scan():
    presence = CardPresence(removal_grace=1.0)
    presence.seen("04AA", 0.0)
    # Karte am Rand des Felds / "Card is unresponsive" für 0,5 s
    presence.not_seen(0.5)
    assert presence.seen("04AA", 0.9) is False


def test_card_lifted_and_placed_again_is_reported_again():
    presence = CardPresence(removal_grace=1.0)
    presence.seen("04AA", 0.0)
    presence.not_seen(0.5)
    presence.not_seen(1.2)
    assert presence.seen("04AA", 2.0) is True


def test_different_card_is_reported_immediately():
    presence = CardPresence(removal_grace=1.0)
    presence.seen("04AA", 0.0)
    assert presence.seen("04BB", 0.3) is True


@pytest.mark.parametrize(
    "message, transient",
    [
        ("Unable to connect with protocol: T0 or T1. Card is unresponsive.: Card is unresponsive. (0x80100066)", True),
        ("Card was removed.", True),
        ("Unable to connect with protocol: T0 or T1. Unknown reader specified. (0x80100009)", False),
    ],
)
def test_transient_card_errors_are_recognized(message, transient):
    assert nfc_bridge._is_transient_card_error(Exception(message)) is transient


def test_watchdog_exits_when_read_loop_hangs(monkeypatch):
    exits = []

    def fake_exit(code):
        exits.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(nfc_bridge.os, "_exit", fake_exit)
    monkeypatch.setattr(nfc_bridge, "release_single_instance_lock", lambda: None)
    monkeypatch.setattr(nfc_bridge.time, "sleep", lambda _seconds: None)

    watchdog = nfc_bridge.Watchdog(timeout=15)
    watchdog.last_beat = nfc_bridge.time.monotonic() - 20  # Schleife hängt seit 20 s
    with pytest.raises(SystemExit):
        watchdog._run()
    assert exits == [3]


def test_watchdog_beat_keeps_process_alive():
    watchdog = nfc_bridge.Watchdog(timeout=15)
    watchdog.last_beat = 0
    watchdog.beat()
    assert nfc_bridge.time.monotonic() - watchdog.last_beat < 1
