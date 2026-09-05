from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.judgment import JudgmentAction, JudgmentInput, JudgmentLevel, JudgmentPolicy


def test_low_risk_read_action_can_proceed_without_disclosure():
    result = JudgmentPolicy().judge(
        JudgmentInput(identity=IdentityLevel.OWNER, permission=Permission.READ)
    )

    assert result.level is JudgmentLevel.SAFE
    assert result.action is JudgmentAction.PROCEED
    assert result.owner_needs_to_know is False


def test_unknown_speaker_cannot_authorize_elevated_action():
    result = JudgmentPolicy().judge(
        JudgmentInput(identity=IdentityLevel.UNKNOWN, permission=Permission.WRITE)
    )

    assert result.level is JudgmentLevel.RISKY
    assert result.action is JudgmentAction.STOP
    assert result.owner_needs_to_know is True


def test_irreversible_action_requires_owner_direction():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.WRITE,
            irreversible=True,
        )
    )

    assert result.level is JudgmentLevel.RISKY
    assert result.action is JudgmentAction.ASK
    assert result.owner_needs_to_know is True


def test_explicit_owner_direction_allows_high_impact_action_to_be_disclosed():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.WRITE,
            material_impact=True,
            explicit_owner_direction=True,
        )
    )

    assert result.action is JudgmentAction.INFORM
    assert result.owner_needs_to_know is True


def test_security_sensitive_action_requires_owner_direction():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.READ,
            affects_security=True,
        )
    )

    assert result.level is JudgmentLevel.RISKY
    assert result.action is JudgmentAction.ASK


def test_privacy_or_external_effect_is_disclosed():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.READ,
            affects_privacy=True,
        )
    )

    assert result.level is JudgmentLevel.QUESTIONABLE
    assert result.action is JudgmentAction.INFORM
    assert result.owner_needs_to_know is True


def test_uncertainty_requires_question_instead_of_guessing():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.READ,
            uncertain=True,
        )
    )

    assert result.level is JudgmentLevel.QUESTIONABLE
    assert result.action is JudgmentAction.ASK
    assert result.owner_needs_to_know is True


def test_potentially_illegal_action_stops():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            potentially_illegal=True,
        )
    )

    assert result.level is JudgmentLevel.ILLEGAL
    assert result.action is JudgmentAction.STOP
    assert result.owner_needs_to_know is True


def test_clearly_harmful_action_stops():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            clearly_harmful=True,
        )
    )

    assert result.level is JudgmentLevel.HARMFUL
    assert result.action is JudgmentAction.STOP
    assert result.owner_needs_to_know is True


def test_elevated_action_is_disclosed_even_when_owner_is_known():
    result = JudgmentPolicy().judge(
        JudgmentInput(
            identity=IdentityLevel.OWNER,
            permission=Permission.EXTERNAL,
        )
    )

    assert result.level is JudgmentLevel.QUESTIONABLE
    assert result.action is JudgmentAction.INFORM
    assert result.owner_needs_to_know is True
