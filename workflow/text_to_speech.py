"""Local-first text-to-speech pipeline for JARVIS.

The implementation keeps synthesis behind a small provider-neutral interface.
The default provider uses pyttsx3, which delegates to the operating system's
installed speech engine and does not require a cloud API or API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any, Protocol
import os


@dataclass(frozen=True)
class SpeechVoice:
    """A speech voice exposed by the local TTS engine."""

    id: str
    name: str
    languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpeechSynthesisResult:
    """Structured result from a TTS operation."""

    success: bool
    text: str
    output_path: str | None = None
    voice: str | None = None
    rate: int | None = None
    error: str | None = None
    cancelled: bool = False


class TextToSpeechError(RuntimeError):
    """Raised when text-to-speech cannot be performed."""


class TextToSpeechProvider(Protocol):
    """Provider contract used by the JARVIS TTS pipeline."""

    def synthesize(self, text: str, output_path: str | Path) -> SpeechSynthesisResult: ...

    def speak(self, text: str, stop_event: Event | None = None) -> SpeechSynthesisResult: ...

    def stop(self) -> None: ...

    def voices(self) -> tuple[SpeechVoice, ...]: ...


class Pyttsx3Synthesizer:
    """Local TTS provider backed by pyttsx3 and the host OS speech engine."""

    def __init__(
        self,
        *,
        voice: str | None = None,
        rate: int | None = None,
        volume: float | None = None,
    ) -> None:
        self.voice = voice or os.getenv("AIOS_TTS_VOICE") or None
        self.rate = rate if rate is not None else int(os.getenv("AIOS_TTS_RATE", "175"))
        self.volume = volume if volume is not None else float(os.getenv("AIOS_TTS_VOLUME", "1.0"))
        self._engine: Any = None
        self._lock = Lock()
        self._speaking = False

    def _load_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        try:
            import pyttsx3
        except ImportError as exc:
            raise TextToSpeechError(
                "pyttsx3 is not installed. Install the TTS dependencies first."
            ) from exc
        try:
            self._engine = pyttsx3.init()
            self._configure(self._engine)
        except Exception as exc:
            raise TextToSpeechError(f"Unable to initialize local TTS engine: {exc}") from exc
        return self._engine

    def _configure(self, engine: Any) -> None:
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", max(0.0, min(1.0, self.volume)))
        if self.voice:
            engine.setProperty("voice", self.voice)

    @staticmethod
    def _validate_text(text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        normalized = text.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        return normalized

    def synthesize(self, text: str, output_path: str | Path) -> SpeechSynthesisResult:
        text = self._validate_text(text)
        destination = Path(output_path)
        if destination.suffix.lower() != ".wav":
            raise ValueError("output_path must use the .wav extension")
        destination.parent.mkdir(parents=True, exist_ok=True)
        engine = self._load_engine()
        with self._lock:
            try:
                self._configure(engine)
                engine.save_to_file(text, str(destination))
                engine.runAndWait()
            except Exception as exc:
                raise TextToSpeechError(f"Speech synthesis failed: {exc}") from exc
        return SpeechSynthesisResult(
            success=True,
            text=text,
            output_path=str(destination),
            voice=self.voice,
            rate=self.rate,
        )

    def speak(self, text: str, stop_event: Event | None = None) -> SpeechSynthesisResult:
        text = self._validate_text(text)
        if stop_event is not None and stop_event.is_set():
            return SpeechSynthesisResult(success=False, text=text, cancelled=True, error="Speech cancelled")
        engine = self._load_engine()
        with self._lock:
            self._speaking = True
            try:
                self._configure(engine)
                engine.say(text)
                engine.runAndWait()
                if stop_event is not None and stop_event.is_set():
                    return SpeechSynthesisResult(success=False, text=text, cancelled=True, error="Speech cancelled")
            except Exception as exc:
                raise TextToSpeechError(f"Speech playback failed: {exc}") from exc
            finally:
                self._speaking = False
        return SpeechSynthesisResult(success=True, text=text, voice=self.voice, rate=self.rate)

    def stop(self) -> None:
        if self._engine is None:
            return
        with self._lock:
            try:
                self._engine.stop()
            except Exception as exc:
                raise TextToSpeechError(f"Unable to stop speech: {exc}") from exc
            finally:
                self._speaking = False

    def voices(self) -> tuple[SpeechVoice, ...]:
        engine = self._load_engine()
        try:
            raw_voices = engine.getProperty("voices") or []
        except Exception as exc:
            raise TextToSpeechError(f"Unable to enumerate speech voices: {exc}") from exc
        result: list[SpeechVoice] = []
        for item in raw_voices:
            languages: list[str] = []
            for language in getattr(item, "languages", ()) or ():
                if isinstance(language, bytes):
                    language = language.decode(errors="ignore")
                languages.append(str(language))
            result.append(
                SpeechVoice(
                    id=str(getattr(item, "id", "")),
                    name=str(getattr(item, "name", getattr(item, "id", ""))),
                    languages=tuple(languages),
                )
            )
        return tuple(result)

    @property
    def speaking(self) -> bool:
        return self._speaking


class TextToSpeechPipeline:
    """High-level JARVIS text-to-speech interface."""

    def __init__(self, provider: TextToSpeechProvider | None = None) -> None:
        self.provider = provider or Pyttsx3Synthesizer()

    def speak(self, text: str, stop_event: Event | None = None) -> SpeechSynthesisResult:
        return self.provider.speak(text, stop_event=stop_event)

    def synthesize(self, text: str, output_path: str | Path) -> SpeechSynthesisResult:
        return self.provider.synthesize(text, output_path)

    def stop(self) -> None:
        self.provider.stop()

    def voices(self) -> tuple[SpeechVoice, ...]:
        return self.provider.voices()


text_to_speech = TextToSpeechPipeline()

__all__ = [
    "Pyttsx3Synthesizer",
    "SpeechSynthesisResult",
    "SpeechVoice",
    "TextToSpeechError",
    "TextToSpeechPipeline",
    "TextToSpeechProvider",
    "text_to_speech",
]
