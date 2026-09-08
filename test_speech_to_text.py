"""Tests for the local speech-to-text foundation."""

from __future__ import annotations

import io
import wave
from threading import Event

import pytest

from workflow.speech_to_text import (
    MicrophoneRecorder,
    SpeechToTextError,
    SpeechToTextPipeline,
    TranscriptSegment,
    TranscriptionResult,
    WhisperTranscriber,
)


class FakeTranscriber:
    def __init__(self) -> None:
        self.inputs = []

    def transcribe(self, audio):
        self.inputs.append(audio)
        return TranscriptionResult(
            text="hello jarvis",
            language="en",
            language_probability=0.99,
            segments=(TranscriptSegment("hello jarvis", 0.0, 1.0),),
        )


class FakeRecorder:
    def __init__(self) -> None:
        self.calls = []

    def record(self, duration, *, stop_event=None):
        self.calls.append((duration, stop_event))
        return b"audio"


def test_transcription_result_is_structured():
    result = TranscriptionResult(
        text="hello",
        language="en",
        language_probability=0.9,
        segments=(TranscriptSegment("hello", 0.0, 0.8),),
    )
    assert result.text == "hello"
    assert result.segments[0].start == 0.0


def test_pipeline_connects_microphone_to_transcriber():
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    pipeline = SpeechToTextPipeline(transcriber=transcriber, recorder=recorder)

    result = pipeline.listen_once(2.5)

    assert result.text == "hello jarvis"
    assert recorder.calls[0][0] == 2.5
    assert transcriber.inputs == [b"audio"]


def test_pipeline_accepts_existing_audio():
    transcriber = FakeTranscriber()
    pipeline = SpeechToTextPipeline(transcriber=transcriber, recorder=FakeRecorder())

    result = pipeline.transcribe_audio(b"recorded audio")

    assert result.text == "hello jarvis"
    assert transcriber.inputs == [b"recorded audio"]


def test_microphone_recorder_rejects_invalid_duration():
    recorder = MicrophoneRecorder()
    with pytest.raises(ValueError):
        recorder.record(0)


def test_whisper_missing_dependency_is_reported(monkeypatch):
    transcriber = WhisperTranscriber()

    def missing_import(*args, **kwargs):
        raise ImportError("missing")

    import builtins

    original = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SpeechToTextError, match="faster-whisper is not installed"):
        transcriber.transcribe(b"audio")


def test_microphone_writes_wav_when_sounddevice_is_available(monkeypatch):
    np = pytest.importorskip("numpy")
    sd = pytest.importorskip("sounddevice")

    monkeypatch.setattr(sd, "rec", lambda frames, samplerate, channels, dtype: np.zeros((frames, channels), dtype=np.int16))
    monkeypatch.setattr(sd, "wait", lambda: None)

    audio = MicrophoneRecorder(sample_rate=8000, channels=1).record(0.01)
    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert wav.getframerate() == 8000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
