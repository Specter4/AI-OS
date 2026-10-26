import pytest

from workflow.voice_interruption import interpret_voice_interruption
from workflow.voice_interaction import VoiceInteractionPipeline
from workflow.text_to_speech import SpeechSynthesisResult


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("Stop talking", "interrupt"),
        ("stop speaking please", "interrupt"),
        ("Wait!", "interrupt"),
        ("hold on a second", "interrupt"),
        ("cancel", "interrupt"),
        ("resume", "resume"),
        ("continue please", "resume"),
        ("Actually, use a shorter answer", "replace"),
        ("No, tell me the summary instead", "replace"),
        ("What time is it?", "none"),
        ("", "none"),
    ],
)
def test_interruption_intents(text, action):
    assert interpret_voice_interruption(text).action == action


def test_non_string_transcript_is_rejected():
    with pytest.raises(TypeError, match="text must be a string"):
        interpret_voice_interruption(None)


class FakeTTS:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True

    def speak(self, text, stop_event=None):
        return SpeechSynthesisResult(success=True, text=text)

    def synthesize(self, text, output_path):
        return SpeechSynthesisResult(success=True, text=text, output_path=str(output_path))

    def voices(self):
        return ()


def test_voice_pipeline_stops_when_barge_in_transcript_requests_stop():
    tts = FakeTTS()
    pipeline = VoiceInteractionPipeline(tts=tts)
    intent = pipeline.handle_interruption_transcript("Stop talking now")
    assert intent.action == "interrupt"
    assert pipeline.stop_event.is_set()
    assert tts.stopped


def test_voice_pipeline_replacement_interrupts_current_turn():
    tts = FakeTTS()
    pipeline = VoiceInteractionPipeline(tts=tts)
    intent = pipeline.handle_interruption_transcript("Actually, make it shorter")
    assert intent.action == "replace"
    assert intent.instruction == "Actually, make it shorter"
    assert pipeline.stop_event.is_set()
    assert tts.stopped


def test_voice_pipeline_resume_clears_interruption_signal():
    pipeline = VoiceInteractionPipeline(tts=FakeTTS())
    pipeline.stop()
    intent = pipeline.handle_interruption_transcript("Continue")
    assert intent.action == "resume"
    assert not pipeline.stop_event.is_set()
