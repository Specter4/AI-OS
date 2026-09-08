"""Compatibility facade for JARVIS audio input and output."""

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

__all__ = [
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
    "WhisperTranscriber",
    "speech_to_text",
    "text_to_speech",
]
