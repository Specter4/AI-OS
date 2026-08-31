import pytest

from core.voice_identity import VoiceIdentity, VoiceIdentityService


def test_high_confidence_voice_is_trusted():
    identity = VoiceIdentity("owner:asif", 0.93, "speaker-verification")
    assert identity.recognized
    assert identity.trusted


def test_low_confidence_voice_is_not_trusted():
    identity = VoiceIdentity("owner:asif", 0.70, "speaker-verification")
    assert identity.recognized
    assert not identity.trusted


def test_unknown_speaker_is_not_recognized():
    identity = VoiceIdentity(None, 0.99)
    assert not identity.recognized
    assert not identity.trusted


def test_service_matches_owner_using_configurable_threshold():
    service = VoiceIdentityService(threshold=0.90)
    identity = service.identify("owner:asif", 0.92, provider="test")
    assert service.is_owner(identity, "owner:asif")
    assert not service.is_owner(identity, "person:friend")


def test_service_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        VoiceIdentityService(threshold=1.1)
    with pytest.raises(ValueError):
        VoiceIdentityService().identify("owner:asif", -0.1)
