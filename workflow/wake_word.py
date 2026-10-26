"""Configurable wake-word activation for JARVIS.

This is a local, provider-neutral activation layer built on the existing STT
pipeline. It uses short microphone windows, so it is a polling wake-word
foundation rather than a dedicated always-on keyword-spotting model.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Callable, Iterable
import os
import re
import time

from workflow.speech_to_text import MicrophoneRecorder, SpeechToTextPipeline, TranscriptionResult


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.casefold()))


@dataclass(frozen=True)
class WakeWordMatch:
    activated: bool
    wake_word: str
    transcript: str
    command: str = ""


class WakeWordDetector:
    """Detect configured wake phrases in a transcript and extract trailing command."""

    def __init__(self, wake_words: Iterable[str] | None = None) -> None:
        configured = wake_words
        if configured is None:
            configured = os.getenv("AIOS_WAKE_WORDS", "jarvis,hey jarvis,ok jarvis").split(",")
        self.wake_words = tuple(
            sorted({_normalize(word) for word in configured if _normalize(word)},
                   key=len, reverse=True)
        )
        if not self.wake_words:
            raise ValueError("at least one non-empty wake word is required")

    def detect(self, transcript: str) -> WakeWordMatch:
        if not isinstance(transcript, str):
            raise TypeError("transcript must be a string")
        normalized = _normalize(transcript)
        for wake_word in self.wake_words:
            # Require a phrase boundary, avoiding accidental matches such as
            # "Jarvis" inside a longer word.
            if normalized == wake_word:
                return WakeWordMatch(True, wake_word, transcript.strip())
            prefix = wake_word + " "
            if normalized.startswith(prefix):
                command = transcript.strip()[len(wake_word):].lstrip(" ,.!?:;-")
                return WakeWordMatch(True, wake_word, transcript.strip(), command)
        return WakeWordMatch(False, "", transcript.strip())


@dataclass(frozen=True)
class WakeWordEvent:
    match: WakeWordMatch
    transcription: TranscriptionResult


class WakeWordListener:
    """Listen in short windows and invoke a callback whenever the wake phrase is heard."""

    def __init__(
        self,
        *,
        stt: SpeechToTextPipeline | None = None,
        recorder: MicrophoneRecorder | None = None,
        detector: WakeWordDetector | None = None,
        window_seconds: float = 2.0,
        cooldown_seconds: float = 1.0,
        on_wake: Callable[[WakeWordEvent], Any] | None = None,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        self.stt = stt or SpeechToTextPipeline()
        self.recorder = recorder or MicrophoneRecorder()
        self.detector = detector or WakeWordDetector()
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.on_wake = on_wake
        self._stop_event = Event()

    @property
    def stop_event(self) -> Event:
        return self._stop_event

    def stop(self) -> None:
        self._stop_event.set()

    def reset(self) -> None:
        self._stop_event.clear()

    def process_audio(self, audio: Any) -> WakeWordEvent | None:
        """Transcribe one supplied audio window and return an event if activated."""
        transcription = self.stt.transcribe_audio(audio)
        match = self.detector.detect(transcription.text)
        if not match.activated:
            return None
        event = WakeWordEvent(match=match, transcription=transcription)
        if self.on_wake is not None:
            self.on_wake(event)
        return event

    def listen(self, *, max_windows: int | None = None) -> int:
        """Poll microphone windows until stopped; return number of activations.

        max_windows is intended for tests and bounded sessions. The default
        listens until stop() is called.
        """
        if max_windows is not None and max_windows < 0:
            raise ValueError("max_windows cannot be negative")
        activations = 0
        windows = 0
        last_activation = float("-inf")
        while not self._stop_event.is_set() and (max_windows is None or windows < max_windows):
            audio = self.recorder.record(self.window_seconds)
            windows += 1
            if self._stop_event.is_set():
                break
            try:
                transcription = self.stt.transcribe_audio(audio)
            except Exception:
                # A noisy/invalid window should not permanently kill the loop.
                continue
            match = self.detector.detect(transcription.text)
            now = time.monotonic()
            if not match.activated or now - last_activation < self.cooldown_seconds:
                continue
            last_activation = now
            activations += 1
            if self.on_wake is not None:
                self.on_wake(WakeWordEvent(match=match, transcription=transcription))
        return activations


__all__ = ["WakeWordDetector", "WakeWordEvent", "WakeWordListener", "WakeWordMatch"]
