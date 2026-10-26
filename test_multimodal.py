from dataclasses import dataclass

from workflow.multimodal import MultimodalInput, MultimodalInteractionPipeline
from workflow.speech_to_text import TranscriptionResult


@dataclass
class FakeConversation:
    success: bool = True
    output: str = "Here is what I found."
    error: str | None = None


class FakeSTT:
    def __init__(self, text="spoken words"):
        self.text = text
        self.calls = []

    def transcribe_audio(self, audio):
        self.calls.append(audio)
        return TranscriptionResult(text=self.text, language="en")


class FakeVision:
    def __init__(self, description="A red mug on a desk"):
        self.description = description
        self.calls = []

    def describe_image(self, image, *, prompt=""):
        self.calls.append((image, prompt))
        return self.description


def test_text_only_turn_uses_conversation_responder():
    prompts = []
    pipeline = MultimodalInteractionPipeline(
        stt=FakeSTT(), responder=lambda message: prompts.append(message) or FakeConversation()
    )
    result = pipeline.process(MultimodalInput(text="Hello"))

    assert result.success
    assert result.modalities == ("text",)
    assert prompts == ["User message: Hello"]


def test_audio_and_text_are_combined_into_one_turn():
    prompts = []
    stt = FakeSTT("what is this?")
    pipeline = MultimodalInteractionPipeline(
        stt=stt, responder=lambda message: prompts.append(message) or FakeConversation()
    )
    result = pipeline.process(MultimodalInput(text="Please answer:", audio=b"audio"))

    assert result.success
    assert result.modalities == ("text", "audio")
    assert "Please answer:" in prompts[0]
    assert "what is this?" in prompts[0]
    assert result.transcription is not None


def test_image_without_provider_fails_transparently():
    pipeline = MultimodalInteractionPipeline(stt=FakeSTT(), responder=lambda message: FakeConversation())
    result = pipeline.process(MultimodalInput(text="What is this?", image=b"image-bytes"))

    assert not result.success
    assert "no image-understanding provider" in result.error
    assert result.response == ""


def test_image_context_is_labeled_and_passed_to_responder():
    prompts = []
    vision = FakeVision()
    pipeline = MultimodalInteractionPipeline(
        stt=FakeSTT(),
        vision=vision,
        responder=lambda message: prompts.append(message) or FakeConversation(),
    )
    result = pipeline.process(MultimodalInput(text="Describe this", image=b"image-bytes"))

    assert result.success
    assert result.modalities == ("text", "image")
    assert "Image context" in prompts[0]
    assert "A red mug on a desk" in prompts[0]
    assert vision.calls == [(b"image-bytes", "Describe this")]


def test_empty_turn_is_rejected():
    pipeline = MultimodalInteractionPipeline(stt=FakeSTT())
    result = pipeline.process(MultimodalInput())

    assert not result.success
    assert "No usable" in result.error


def test_vision_provider_errors_are_reported():
    class BrokenVision:
        def describe_image(self, image, *, prompt=""):
            raise RuntimeError("model unavailable")

    pipeline = MultimodalInteractionPipeline(vision=BrokenVision())
    result = pipeline.process(MultimodalInput(image=b"image"))

    assert not result.success
    assert "model unavailable" in result.error


def test_speak_requires_configured_tts():
    pipeline = MultimodalInteractionPipeline(stt=FakeSTT(), responder=lambda message: FakeConversation())
    result = pipeline.process(MultimodalInput(text="Hello"), speak=True)

    assert not result.success
    assert "no text-to-speech pipeline" in result.error
    assert result.response == "Here is what I found."
