"""Natural voice interaction pipeline for JARVIS.

Combines microphone capture, local speech-to-text, conversational reasoning,
and text-to-speech behind one interruption-ready interface.  The pipeline is
provider-neutral at its boundaries so later voice providers can replace the
local defaults without changing conversation code.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Protocol

from conversation.engine import respond
from workflow.speech_to_text import MicrophoneRecorder, SpeechToTextPipeline, TranscriptionResult
from workflow.text_to_speech import SpeechSynthesisResult, TextToSpeechPipeline


@dataclass(frozen=True)
class VoiceInteractionResult:
    """Structured result for one complete voice turn."""

    success: bool
    transcript: str = ""
    response: str = ""
    speech: SpeechSynthesisResult | None = None
    transcription: TranscriptionResult | None = None
    error: str | None = None
    cancelled: bool = False


class ConversationResponder(Protocol):
    def __call__(self, message: str, *, goal: bool = False) -> Any: ...


class VoiceInteractionPipeline:
    """Run a natural listen -> understand -> respond -> speak voice turn."""

    def __init__(
        self,
        *,
        stt: SpeechToTextPipeline | None = None,
        tts: TextToSpeechPipeline | None = None,
        responder: ConversationResponder = respond,
    ) -> None:
        self.stt = stt or SpeechToTextPipeline()
        self.tts = tts or TextToSpeechPipeline()
        self.responder = responder
        self._stop_event = Event()

    @property
    def stop_event(self) -> Event:
        return self._stop_event

    def stop(self) -> None:
        """Stop the current voice turn and any active speech playback."""
        self._stop_event.set()
        self.tts.stop()

    def reset(self) -> None:
        """Clear a previous stop signal before starting a new turn."""
        self._stop_event.clear()

    def process_audio(self, audio: Any, *, language: str | None = None) -> VoiceInteractionResult:
        """Process an audio path/bytes object into a spoken conversational reply."""
        if self._stop_event.is_set():
            return VoiceInteractionResult(success=False, cancelled=True, error="Voice interaction cancelled")

        try:
            transcription = self.stt.transcribe(audio, language=language)
        except Exception as exc:
            return VoiceInteractionResult(success=False, error=str(exc))

        if not transcription.success or not transcription.text.strip():
            return VoiceInteractionResult(
                success=False,
                transcription=transcription,
                error=transcription.error or "No speech was detected",
            )

        if self._stop_event.is_set():
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                transcription=transcription,
                cancelled=True,
                error="Voice interaction cancelled",
            )

        try:
            conversational = self.responder(transcription.text)
        except Exception as exc:
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                transcription=transcription,
                error=str(exc),
            )

        if not getattr(conversational, "success", False):
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                transcription=transcription,
                error=getattr(conversational, "error", None) or "Conversation response failed",
            )

        response_text = str(getattr(conversational, "output", "")).strip()
        if not response_text:
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                transcription=transcription,
                error="Conversation response was empty",
            )

        if self._stop_event.is_set():
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                response=response_text,
                transcription=transcription,
                cancelled=True,
                error="Voice interaction cancelled",
            )

        try:
            speech = self.tts.speak(response_text, stop_event=self._stop_event)
        except Exception as exc:
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                response=response_text,
                transcription=transcription,
                error=str(exc),
            )

        if speech.cancelled:
            return VoiceInteractionResult(
                success=False,
                transcript=transcription.text,
                response=response_text,
                transcription=transcription,
                speech=speech,
                cancelled=True,
                error=speech.error or "Speech cancelled",
            )

        return VoiceInteractionResult(
            success=True,
            transcript=transcription.text,
            response=response_text,
            transcription=transcription,
            speech=speech,
        )

    def listen_once(
        self,
        *,
        duration: float | None = None,
        language: str | None = None,
        recorder: MicrophoneRecorder | None = None,
    ) -> VoiceInteractionResult:
        """Record one microphone turn and process it conversationally."""
        if self._stop_event.is_set():
            return VoiceInteractionResult(success=False, cancelled=True, error="Voice interaction cancelled")
        microphone = recorder or MicrophoneRecorder()
        try:
            audio = microphone.record(duration=duration, stop_event=self._stop_event)
        except Exception as exc:
            return VoiceInteractionResult(success=False, error=str(exc))
        if audio is None:
            return VoiceInteractionResult(success=False, cancelled=self._stop_event.is_set(), error="No audio was recorded")
        return self.process_audio(audio, language=language)


voice_interaction = VoiceInteractionPipeline()

__all__ = ["ConversationResponder", "VoiceInteractionPipeline", "VoiceInteractionResult", "voice_interaction"]
