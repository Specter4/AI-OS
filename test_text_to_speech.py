"""Tests for the Phase 8 Step 2 text-to-speech layer."""

from pathlib import Path
from threading import Event

import pytest

import workflow.text_to_speech as tts


class FakeProvider:
    def __init__(self) -> None:
        self.calls = []
        self.stopped = False

    def synthesize(self, text, output_path):
        self.calls.append(("synthesize", text, str(output_path)))
        return tts.SpeechSynthesisResult(True, text, str(output_path), "fake", 180)

    def speak(self, text, stop_event=None):
        self.calls.append(("speak", text, stop_event))
        if stop_event is not None and stop_event.is_set():
            return tts.SpeechSynthesisResult(False, text, error="Speech cancelled", cancelled=True)
        return tts.SpeechSynthesisResult(True, text, voice="fake", rate=180)

    def stop(self):
        self.stopped = True

    def voices(self):
        return (tts.SpeechVoice("fake-id", "Fake Voice", ("en",)),)


def test_pipeline_delegates_speak_and_synthesize(tmp_path: Path):
    provider = FakeProvider()
    pipeline = tts.TextToSpeechPipeline(provider)

    spoken = pipeline.speak("Hello Asif")
    output = pipeline.synthesize("Saved speech", tmp_path / "speech.wav")

    assert spoken.success is True
    assert spoken.voice == "fake"
    assert output.output_path.endswith("speech.wav")
    assert provider.calls[0][:2] == ("speak", "Hello Asif")
    assert provider.calls[1][:2] == ("synthesize", "Saved speech")


def test_pipeline_supports_stop_and_voice_listing():
    provider = FakeProvider()
    pipeline = tts.TextToSpeechPipeline(provider)

    pipeline.stop()

    assert provider.stopped is True
    assert pipeline.voices()[0].name == "Fake Voice"


def test_cancelled_speak_is_reported():
    provider = FakeProvider()
    pipeline = tts.TextToSpeechPipeline(provider)
    event = Event()
    event.set()

    result = pipeline.speak("Stop speaking", stop_event=event)

    assert result.success is False
    assert result.cancelled is True


def test_text_validation():
    provider = FakeProvider()
    synthesizer = tts.Pyttsx3Synthesizer()

    with pytest.raises(ValueError, match="must not be empty"):
        synthesizer._validate_text("   ")
    with pytest.raises(TypeError, match="must be a string"):
        synthesizer._validate_text(None)  # type: ignore[arg-type]

    assert provider is not None


def test_synthesize_requires_wav_extension(tmp_path: Path):
    synthesizer = tts.Pyttsx3Synthesizer()

    with pytest.raises(ValueError, match=".wav extension"):
        synthesizer.synthesize("Hello", tmp_path / "speech.mp3")


def test_missing_pyttsx3_has_clear_error(monkeypatch):
    synthesizer = tts.Pyttsx3Synthesizer()

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "pyttsx3":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)

    with pytest.raises(tts.TextToSpeechError, match="pyttsx3 is not installed"):
        synthesizer._load_engine()
