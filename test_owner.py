from core.owner import OwnerIdentity, load_owner


def test_owner_defaults_to_asif():
    identity = load_owner()
    assert identity.name == "Asif"
    assert identity.owner_id == "owner:asif"
    assert identity.role == "owner"


def test_owner_identity_matches_stable_id():
    identity = OwnerIdentity("Asif", "owner:asif")
    assert identity.matches("owner:asif")
    assert identity.matches(" OWNER:ASIF ")
    assert not identity.matches("person:friend")
    assert not identity.matches(None)


def test_owner_authorization_context_is_explicit():
    identity = OwnerIdentity("Asif", "owner:asif")
    assert identity.authorization_context() == {
        "owner_name": "Asif",
        "owner_id": "owner:asif",
        "role": "owner",
    }
