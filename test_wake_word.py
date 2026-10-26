from workflow.speech_to_text import TranscriptionResult
from workflow.wake_word import WakeWordDetector, WakeWordEvent, WakeWordListener


def test_detector_matches_default_jarvis_wake_word():
    match = WakeWordDetector().detect("Jarvis")
    assert match.activated
    assert match.wake_word == "jarvis"
    assert match.command == ""


def test_detector_extracts_command_after_wake_phrase():
    match = WakeWordDetector(["hey jarvis"]).detect("Hey Jarvis, what time is it?")
    assert match.activated
    assert match.wake_word == "hey jarvis"
    assert match.command == "what time is it?"


def test_detector_does_not_match_inside_another_word():
    assert not WakeWordDetector(["jarvis"]).detect("Jarvisian architecture").activated


def test_detector_normalizes_case_and_punctuation():
    assert WakeWordDetector(["OK Jarvis"]).detect("OK, Jarvis!").activated


def test_detector_requires_at_least_one_wake_word():
    try:
        WakeWordDetector(["", "   "])
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("Expected empty wake word configuration to fail")


class FakeSTT:
    def __init__(self, texts):
        self.texts = iter(texts)

    def transcribe_audio(self, audio):
        return TranscriptionResult(text=next(self.texts))


class FakeRecorder:
    def __init__(self, windows):
        self.windows = iter(windows)
        self.calls = 0

    def record(self, duration):
        self.calls += 1
        return next(self.windows)


def test_listener_emits_wake_event_and_continues():
    events = []
    listener = WakeWordListener(
        stt=FakeSTT(["background noise", "Jarvis, open settings"]),
        recorder=FakeRecorder([b"window-1", b"window-2"]),
        window_seconds=0.1,
        cooldown_seconds=0,
        on_wake=events.append,
    )
    assert listener.listen(max_windows=2) == 1
    assert len(events) == 1
    assert isinstance(events[0], WakeWordEvent)
    assert events[0].match.command == "open settings"


def test_listener_can_be_stopped_before_listening():
    listener = WakeWordListener(
        stt=FakeSTT([]),
        recorder=FakeRecorder([]),
    )
    listener.stop()
    assert listener.listen() == 0


def test_listener_validates_window_and_cooldown():
    try:
        WakeWordListener(window_seconds=0)
    except ValueError as exc:
        assert "window_seconds" in str(exc)
    else:
        raise AssertionError("Expected invalid window to fail")

    try:
        WakeWordListener(cooldown_seconds=-1)
    except ValueError as exc:
        assert "cooldown_seconds" in str(exc)
    else:
        raise AssertionError("Expected invalid cooldown to fail")
