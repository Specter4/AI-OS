"""Compatibility facade for JARVIS audio input."""

from workflow.speech_to_text import (
    MicrophoneRecorder,
    SpeechToTextError,
    SpeechToTextPipeline,
    TranscriptSegment,
    TranscriptionResult,
    WhisperTranscriber,
    speech_to_text,
)

__all__ = [
    "MicrophoneRecorder",
    "SpeechToTextError",
    "SpeechToTextPipeline",
    "TranscriptSegment",
    "TranscriptionResult",
    "WhisperTranscriber",
    "speech_to_text",
]
