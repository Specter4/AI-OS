from dataclasses import dataclass

import pytest

from workflow.speech_to_text import TranscriptionResult
from workflow.text_to_speech import SpeechSynthesisResult
from workflow.voice_interaction import VoiceInteractionPipeline


@dataclass
class FakeConversation:
    success: bool = True
    output: str = "Hello, Asif."
    error: str | None = None


class FakeSTT:
    def __init__(self, text="hello jarvis"):
        self.text = text
        self.calls = []

    def transcribe_audio(self, audio):
        self.calls.append(audio)
        return TranscriptionResult(text=self.text, language="en")


class FakeTTS:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled
        self.calls = []
        self.stopped = False

    def speak(self, text, stop_event=None):
        self.calls.append((text, stop_event))
        return SpeechSynthesisResult(
            success=not self.cancelled,
            text=text,
            cancelled=self.cancelled,
            error="Speech cancelled" if self.cancelled else None,
        )

    def stop(self):
        self.stopped = True


def test_voice_turn_runs_stt_conversation_and_tts_in_order():
    stt = FakeSTT("what is the weather")
    tts = FakeTTS()
    seen = []

    def responder(message, *, goal=False):
        seen.append((message, goal))
        return FakeConversation(output="It looks clear.")

    pipeline = VoiceInteractionPipeline(stt=stt, tts=tts, responder=responder)
    result = pipeline.process_audio(b"audio")

    assert result.success
    assert result.transcript == "what is the weather"
    assert result.response == "It looks clear."
    assert seen == [("what is the weather", False)]
    assert tts.calls[0][0] == "It looks clear."


def test_empty_transcript_does_not_call_responder_or_tts():
    stt = FakeSTT("")
    tts = FakeTTS()
    calls = []

    pipeline = VoiceInteractionPipeline(stt=stt, tts=tts, responder=lambda message: calls.append(message))
    result = pipeline.process_audio(b"audio")

    assert not result.success
    assert result.error == "No speech was detected"
    assert calls == []
    assert tts.calls == []


def test_failed_conversation_is_not_spoken():
    stt = FakeSTT("do something")
    tts = FakeTTS()

    pipeline = VoiceInteractionPipeline(
        stt=stt,
        tts=tts,
        responder=lambda message: FakeConversation(success=False, output="", error="LLM unavailable"),
    )
    result = pipeline.process_audio(b"audio")

    assert not result.success
    assert result.error == "LLM unavailable"
    assert tts.calls == []


def test_cancelled_speech_is_reported():
    stt = FakeSTT("hello")
    tts = FakeTTS(cancelled=True)
    pipeline = VoiceInteractionPipeline(stt=stt, tts=tts, responder=lambda message: FakeConversation())

    result = pipeline.process_audio(b"audio")

    assert not result.success
    assert result.cancelled
    assert result.speech is not None
    assert result.speech.cancelled


def test_stop_sets_signal_and_stops_tts():
    tts = FakeTTS()
    pipeline = VoiceInteractionPipeline(stt=FakeSTT(), tts=tts, responder=lambda message: FakeConversation())

    pipeline.stop()

    assert pipeline.stop_event.is_set()
    assert tts.stopped


def test_reset_clears_stop_signal():
    pipeline = VoiceInteractionPipeline(stt=FakeSTT(), tts=FakeTTS(), responder=lambda message: FakeConversation())
    pipeline.stop()
    pipeline.reset()
    assert not pipeline.stop_event.is_set()


def test_listen_once_rejects_non_positive_duration():
    pipeline = VoiceInteractionPipeline(stt=FakeSTT(), tts=FakeTTS(), responder=lambda message: FakeConversation())
    with pytest.raises(ValueError, match="duration must be positive"):
        pipeline.listen_once(0)


def test_listen_once_processes_recorded_audio():
    class Recorder:
        def record(self, duration, *, stop_event=None):
            assert duration == 1.5
            return b"recorded"

    stt = FakeSTT("hello")
    tts = FakeTTS()
    pipeline = VoiceInteractionPipeline(stt=stt, tts=tts, responder=lambda message: FakeConversation(output="Hi there."))

    result = pipeline.listen_once(1.5, recorder=Recorder())

    assert result.success
    assert stt.calls == [b"recorded"]
    assert tts.calls[0][0] == "Hi there."
