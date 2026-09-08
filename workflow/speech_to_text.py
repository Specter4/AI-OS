"""Local-first speech-to-text pipeline for JARVIS.

The module keeps audio capture separate from transcription so the same STT
engine can consume microphone recordings, uploaded audio, or programmatic
PCM/WAV data. The default implementation uses faster-whisper when installed;
no cloud API is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Iterable
import io
import os
import wave


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None = None
    language_probability: float | None = None
    segments: tuple[TranscriptSegment, ...] = ()


class SpeechToTextError(RuntimeError):
    """Raised when speech-to-text cannot be performed."""


class WhisperTranscriber:
    """Lazy-loaded faster-whisper transcriber with configurable local models."""

    def __init__(
        self,
        model_size: str | None = None,
        *,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
        beam_size: int = 5,
    ) -> None:
        self.model_size = model_size or os.getenv("AIOS_STT_MODEL", "small")
        self.device = device or os.getenv("AIOS_STT_DEVICE", "auto")
        self.compute_type = compute_type or os.getenv("AIOS_STT_COMPUTE_TYPE", "auto")
        self.language = language or os.getenv("AIOS_STT_LANGUAGE") or None
        self.beam_size = beam_size
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechToTextError(
                "faster-whisper is not installed. Install the STT dependencies first."
            ) from exc

        device = self.device
        compute_type = self.compute_type
        if device == "auto":
            device = "cuda" if self._cuda_available() else "cpu"
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

        try:
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:
            raise SpeechToTextError(f"Unable to load STT model '{self.model_size}': {exc}") from exc
        return self._model

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def transcribe(self, audio: str | Path | bytes | bytearray) -> TranscriptionResult:
        """Transcribe an audio file path or encoded audio bytes."""
        model = self._load_model()
        source: Any = audio
        temporary_stream: io.BytesIO | None = None
        if isinstance(audio, (bytes, bytearray)):
            temporary_stream = io.BytesIO(bytes(audio))
            source = temporary_stream

        try:
            segments, info = model.transcribe(
                source,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=True,
            )
            parsed = tuple(
                TranscriptSegment(
                    text=segment.text.strip(),
                    start=float(segment.start),
                    end=float(segment.end),
                )
                for segment in segments
                if segment.text.strip()
            )
        except Exception as exc:
            raise SpeechToTextError(f"Transcription failed: {exc}") from exc
        finally:
            if temporary_stream is not None:
                temporary_stream.close()

        return TranscriptionResult(
            text=" ".join(segment.text for segment in parsed).strip(),
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            segments=parsed,
        )


class MicrophoneRecorder:
    """Small blocking microphone recorder using sounddevice when available."""

    def __init__(self, *, sample_rate: int = 16_000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels

    def record(self, duration: float, *, stop_event: Event | None = None) -> bytes:
        if duration <= 0:
            raise ValueError("duration must be positive")
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechToTextError(
                "Microphone capture requires sounddevice and numpy."
            ) from exc

        frames = int(self.sample_rate * duration)
        try:
            audio = sd.rec(frames, samplerate=self.sample_rate, channels=self.channels, dtype="int16")
            if stop_event is None:
                sd.wait()
            else:
                while not stop_event.is_set():
                    sd.sleep(50)
                sd.stop()
            samples = np.asarray(audio, dtype=np.int16)
        except Exception as exc:
            raise SpeechToTextError(f"Microphone recording failed: {exc}") from exc

        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples.tobytes())
        return output.getvalue()


class SpeechToTextPipeline:
    """Microphone/audio -> transcript pipeline."""

    def __init__(self, transcriber: WhisperTranscriber | None = None, recorder: MicrophoneRecorder | None = None) -> None:
        self.transcriber = transcriber or WhisperTranscriber()
        self.recorder = recorder or MicrophoneRecorder()

    def transcribe_audio(self, audio: str | Path | bytes | bytearray) -> TranscriptionResult:
        return self.transcriber.transcribe(audio)

    def listen_once(self, duration: float, *, stop_event: Event | None = None) -> TranscriptionResult:
        audio = self.recorder.record(duration, stop_event=stop_event)
        return self.transcriber.transcribe(audio)


speech_to_text = SpeechToTextPipeline()

__all__ = [
    "MicrophoneRecorder",
    "SpeechToTextError",
    "SpeechToTextPipeline",
    "TranscriptSegment",
    "TranscriptionResult",
    "WhisperTranscriber",
    "speech_to_text",
]
