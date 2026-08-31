import pytest

from core.face_identity import FaceIdentity, FaceIdentityService


def test_high_confidence_face_is_trusted():
    identity = FaceIdentity("owner:asif", 0.94, "face-verification")
    assert identity.recognized
    assert identity.trusted


def test_low_confidence_face_is_not_trusted():
    identity = FaceIdentity("owner:asif", 0.70, "face-verification")
    assert identity.recognized
    assert not identity.trusted


def test_unknown_face_is_not_recognized():
    identity = FaceIdentity(None, 0.99)
    assert not identity.recognized
    assert not identity.trusted


def test_service_matches_owner_using_threshold():
    service = FaceIdentityService(threshold=0.90)
    identity = service.identify("owner:asif", 0.92, provider="test")
    assert service.is_owner(identity, "owner:asif")
    assert not service.is_owner(identity, "person:friend")


def test_service_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        FaceIdentityService(threshold=1.1)
    with pytest.raises(ValueError):
        FaceIdentityService().identify("owner:asif", -0.1)
