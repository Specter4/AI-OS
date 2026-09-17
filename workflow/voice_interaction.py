"""Natural voice interaction pipeline for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Protocol

from conversation.engine import respond
from workflow.speech_to_text import MicrophoneRecorder, SpeechToTextPipeline, TranscriptionResult
from workflow.text_to_speech import SpeechSynthesisResult, TextToSpeechPipeline


@dataclass(frozen=True)
class VoiceInteractionResult:
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
    """Run one natural listen -> understand -> respond -> speak turn."""

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
        self._stop_event.set()
        self.tts.stop()

    def reset(self) -> None:
        self._stop_event.clear()

    def process_audio(self, audio: Any) -> VoiceInteractionResult:
        """Transcribe audio, generate a conversational response, then speak it."""
        if self._stop_event.is_set():
            return VoiceInteractionResult(False, cancelled=True, error="Voice interaction cancelled")
        try:
            transcription = self.stt.transcribe_audio(audio)
        except Exception as exc:
            return VoiceInteractionResult(False, error=str(exc))

        transcript = transcription.text.strip()
        if not transcript:
            return VoiceInteractionResult(False, transcription=transcription, error="No speech was detected")
        if self._stop_event.is_set():
            return VoiceInteractionResult(False, transcript=transcript, transcription=transcription, cancelled=True, error="Voice interaction cancelled")

        try:
            conversational = self.responder(transcript)
        except Exception as exc:
            return VoiceInteractionResult(False, transcript=transcript, transcription=transcription, error=str(exc))
        if not getattr(conversational, "success", False):
            return VoiceInteractionResult(
                False, transcript=transcript, transcription=transcription,
                error=getattr(conversational, "error", None) or "Conversation response failed",
            )

        response_text = str(getattr(conversational, "output", "")).strip()
        if not response_text:
            return VoiceInteractionResult(False, transcript=transcript, transcription=transcription, error="Conversation response was empty")
        if self._stop_event.is_set():
            return VoiceInteractionResult(False, transcript=transcript, response=response_text, transcription=transcription, cancelled=True, error="Voice interaction cancelled")

        try:
            speech = self.tts.speak(response_text, stop_event=self._stop_event)
        except Exception as exc:
            return VoiceInteractionResult(False, transcript=transcript, response=response_text, transcription=transcription, error=str(exc))
        if speech.cancelled:
            return VoiceInteractionResult(False, transcript=transcript, response=response_text, transcription=transcription, speech=speech, cancelled=True, error=speech.error or "Speech cancelled")
        return VoiceInteractionResult(True, transcript=transcript, response=response_text, transcription=transcription, speech=speech)

    def listen_once(self, duration: float, *, recorder: MicrophoneRecorder | None = None) -> VoiceInteractionResult:
        """Record one microphone turn and process it conversationally."""
        if duration <= 0:
            raise ValueError("duration must be positive")
        if self._stop_event.is_set():
            return VoiceInteractionResult(False, cancelled=True, error="Voice interaction cancelled")
        microphone = recorder or MicrophoneRecorder()
        try:
            audio = microphone.record(duration, stop_event=self._stop_event)
        except Exception as exc:
            return VoiceInteractionResult(False, error=str(exc))
        if self._stop_event.is_set():
            return VoiceInteractionResult(False, cancelled=True, error="Voice interaction cancelled")
        return self.process_audio(audio)


voice_interaction = VoiceInteractionPipeline()

__all__ = ["ConversationResponder", "VoiceInteractionPipeline", "VoiceInteractionResult", "voice_interaction"]
