"""Provider-neutral multimodal input orchestration for JARVIS.

This module coordinates text, audio, and image inputs without pretending that
an image has been understood when no vision provider is configured. Actual
camera capture and model-specific vision integrations are supplied through
adapters rather than hard-coded dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from conversation.engine import respond
from workflow.speech_to_text import SpeechToTextPipeline, TranscriptionResult
from workflow.text_to_speech import SpeechSynthesisResult, TextToSpeechPipeline


class ImageUnderstandingProvider(Protocol):
    """Adapter contract for a configured image-understanding model."""

    def describe_image(self, image: bytes | str | Path, *, prompt: str = "") -> str: ...


@dataclass(frozen=True)
class MultimodalInput:
    """One user turn that can contain any combination of supported modalities."""

    text: str = ""
    audio: Any | None = None
    image: bytes | str | Path | None = None
    source: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MultimodalInteractionResult:
    success: bool
    user_text: str = ""
    image_description: str = ""
    response: str = ""
    transcription: TranscriptionResult | None = None
    speech: SpeechSynthesisResult | None = None
    modalities: tuple[str, ...] = ()
    error: str | None = None


class MultimodalInteractionPipeline:
    """Combine text/audio/image context into one conversational turn.

    Text and audio use the existing STT interface. Image interpretation
    requires an explicitly configured provider. The responder receives
    clearly labeled context while the existing conversation engine remains
    responsible for conversational behavior.
    """

    def __init__(
        self,
        *,
        stt: SpeechToTextPipeline | None = None,
        vision: ImageUnderstandingProvider | None = None,
        responder: Any = respond,
        tts: TextToSpeechPipeline | None = None,
    ) -> None:
        self.stt = stt or SpeechToTextPipeline()
        self.vision = vision
        self.responder = responder
        self.tts = tts

    def process(self, request: MultimodalInput, *, speak: bool = False) -> MultimodalInteractionResult:
        if not isinstance(request, MultimodalInput):
            raise TypeError("request must be a MultimodalInput")
        text = request.text.strip()
        transcription = None
        modalities: list[str] = []
        if text:
            modalities.append("text")

        if request.audio is not None:
            try:
                transcription = self.stt.transcribe_audio(request.audio)
            except Exception as exc:
                return MultimodalInteractionResult(
                    False, user_text=text, error=f"Audio transcription failed: {exc}"
                )
            spoken_text = transcription.text.strip()
            if spoken_text:
                text = f"{text}\n{spoken_text}".strip() if text else spoken_text
                modalities.append("audio")

        description = ""
        if request.image is not None:
            modalities.append("image")
            if self.vision is None:
                return MultimodalInteractionResult(
                    False, user_text=text, transcription=transcription,
                    modalities=tuple(modalities),
                    error="Image input was received, but no image-understanding provider is configured.",
                )
            try:
                description = str(self.vision.describe_image(request.image, prompt=text)).strip()
            except Exception as exc:
                return MultimodalInteractionResult(
                    False, user_text=text, transcription=transcription,
                    modalities=tuple(modalities), error=f"Image understanding failed: {exc}",
                )
            if not description:
                return MultimodalInteractionResult(
                    False, user_text=text, transcription=transcription,
                    modalities=tuple(modalities),
                    error="Image-understanding provider returned an empty description.",
                )

        if not text and not description:
            return MultimodalInteractionResult(
                False, error="No usable text, audio transcript, or image was provided."
            )

        prompt_parts = []
        if text:
            prompt_parts.append(f"User message: {text}")
        if description:
            prompt_parts.append(f"Image context (provider-generated description): {description}")
        prompt = "\n\n".join(prompt_parts)
        try:
            conversation = self.responder(prompt)
        except Exception as exc:
            return MultimodalInteractionResult(
                False, user_text=text, image_description=description,
                transcription=transcription, modalities=tuple(modalities),
                error=f"Conversation response failed: {exc}",
            )
        if not getattr(conversation, "success", False):
            return MultimodalInteractionResult(
                False, user_text=text, image_description=description,
                transcription=transcription, modalities=tuple(modalities),
                error=getattr(conversation, "error", None) or "Conversation response failed",
            )
        response_text = str(getattr(conversation, "output", "")).strip()
        if not response_text:
            return MultimodalInteractionResult(
                False, user_text=text, image_description=description,
                transcription=transcription, modalities=tuple(modalities),
                error="Conversation response was empty.",
            )

        speech = None
        if speak:
            if self.tts is None:
                return MultimodalInteractionResult(
                    False, user_text=text, image_description=description, response=response_text,
                    transcription=transcription, modalities=tuple(modalities),
                    error="Speech output was requested, but no text-to-speech pipeline is configured.",
                )
            try:
                speech = self.tts.speak(response_text)
            except Exception as exc:
                return MultimodalInteractionResult(
                    False, user_text=text, image_description=description, response=response_text,
                    transcription=transcription, modalities=tuple(modalities),
                    error=f"Speech synthesis failed: {exc}",
                )
            if not speech.success:
                return MultimodalInteractionResult(
                    False, user_text=text, image_description=description, response=response_text,
                    transcription=transcription, speech=speech, modalities=tuple(modalities),
                    error=speech.error or "Speech synthesis failed.",
                )
        return MultimodalInteractionResult(
            True, user_text=text, image_description=description, response=response_text,
            transcription=transcription, speech=speech, modalities=tuple(modalities),
        )


__all__ = [
    "ImageUnderstandingProvider",
    "MultimodalInput",
    "MultimodalInteractionPipeline",
    "MultimodalInteractionResult",
]
