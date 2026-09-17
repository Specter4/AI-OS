"""Compatibility facade for JARVIS audio input, output, and interaction."""

from workflow.speech_to_text import (
    MicrophoneRecorder,
    SpeechToTextError,
    SpeechToTextPipeline,
    TranscriptSegment,
    TranscriptionResult,
    WhisperTranscriber,
    speech_to_text,
)
from workflow.text_to_speech import (
    Pyttsx3Synthesizer,
    SpeechSynthesisResult,
    SpeechVoice,
    TextToSpeechError,
    TextToSpeechPipeline,
    text_to_speech,
)
from workflow.voice_interaction import (
    ConversationResponder,
    VoiceInteractionPipeline,
    VoiceInteractionResult,
    voice_interaction,
)

__all__ = [
    "ConversationResponder",
    "MicrophoneRecorder",
    "Pyttsx3Synthesizer",
    "SpeechSynthesisResult",
    "SpeechToTextError",
    "SpeechToTextPipeline",
    "SpeechVoice",
    "TextToSpeechError",
    "TextToSpeechPipeline",
    "TranscriptSegment",
    "TranscriptionResult",
    "VoiceInteractionPipeline",
    "VoiceInteractionResult",
    "WhisperTranscriber",
    "speech_to_text",
    "text_to_speech",
    "voice_interaction",
]
