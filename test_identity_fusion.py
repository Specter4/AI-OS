from core.authorization import IdentityLevel
from core.identity_fusion import IdentityEvidence, IdentityFusion


def test_voice_and_face_fuse_to_owner():
    fusion = IdentityFusion()
    result = fusion.resolve(
        [
            IdentityEvidence("voice", "owner:asif", 0.94),
            IdentityEvidence("face", "owner:asif", 0.91),
        ],
        owner_id="owner:asif",
    )
    assert result.person_id == "owner:asif"
    assert result.level is IdentityLevel.OWNER
    assert set(result.sources) == {"voice", "face"}
    assert not result.needs_identification


def test_known_person_is_resolved_but_not_owner():
    result = IdentityFusion().resolve(
        [IdentityEvidence("voice", "person:rahim", 0.92)],
        known_person_ids={"person:rahim"},
        owner_id="owner:asif",
    )
    assert result.level is IdentityLevel.KNOWN
    assert result.person_id == "person:rahim"


def test_conflicting_voice_and_face_becomes_unknown():
    result = IdentityFusion().resolve(
        [
            IdentityEvidence("voice", "person:rahim", 0.96),
            IdentityEvidence("face", "person:samia", 0.95),
        ],
        known_person_ids={"person:rahim", "person:samia"},
        owner_id="owner:asif",
    )
    assert result.level is IdentityLevel.UNKNOWN
    assert result.person_id is None
    assert result.needs_identification


def test_low_confidence_identity_requires_identification():
    result = IdentityFusion().resolve(
        [IdentityEvidence("voice", "owner:asif", 0.50)],
        owner_id="owner:asif",
    )
    assert result.level is IdentityLevel.UNKNOWN
    assert result.person_id is None
    assert result.needs_identification


def test_unregistered_person_is_not_promoted_to_known():
    result = IdentityFusion().resolve(
        [IdentityEvidence("face", "person:new", 0.93)],
        known_person_ids=set(),
        owner_id="owner:asif",
    )
    assert result.level is IdentityLevel.UNKNOWN
    assert result.person_id == "person:new"
    assert result.needs_identification
