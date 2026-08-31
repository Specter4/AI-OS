from core.authorization import IdentityLevel, AuthorizationPolicy
from core.tool_registry import Permission


def test_owner_can_read_without_approval():
    decision = AuthorizationPolicy().decide(IdentityLevel.OWNER, Permission.READ)
    assert decision.allowed
    assert not decision.requires_approval


def test_known_person_requires_owner_approval_for_external_action():
    decision = AuthorizationPolicy().decide(IdentityLevel.KNOWN, Permission.EXTERNAL)
    assert not decision.allowed
    assert decision.requires_approval
    assert "owner approval" in decision.reason.lower()


def test_unknown_person_cannot_authorize_write_or_destructive_actions():
    policy = AuthorizationPolicy()
    for permission in (Permission.WRITE, Permission.EXTERNAL, Permission.DESTRUCTIVE):
        decision = policy.decide(IdentityLevel.UNKNOWN, permission)
        assert not decision.allowed
        assert not decision.requires_approval


def test_unknown_person_can_request_read_only_information():
    decision = AuthorizationPolicy().decide(IdentityLevel.UNKNOWN, Permission.READ)
    assert decision.allowed
