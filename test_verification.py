from workflow.verification import VerificationRequest, VerificationStatus, Verifier


def test_matching_expected_output_is_verified():
    result = Verifier().verify(VerificationRequest(action="write", expected="ok", actual="ok"))
    assert result.status == VerificationStatus.VERIFIED
    assert result.verified is True


def test_mismatched_expected_output_fails_verification():
    result = Verifier().verify(VerificationRequest(action="write", expected="ok", actual="wrong"))
    assert result.status == VerificationStatus.FAILED
    assert result.verified is False


def test_custom_postcondition_is_supported():
    result = Verifier().verify(
        VerificationRequest(action="write", actual={"status": "ok"}, check=lambda value: value["status"] == "ok")
    )
    assert result.status == VerificationStatus.VERIFIED


def test_no_postcondition_is_skipped_not_verified():
    result = Verifier().verify(VerificationRequest(action="write", actual="ok"))
    assert result.status == VerificationStatus.SKIPPED
    assert result.verified is False


def test_failed_check_becomes_failed_verification():
    result = Verifier().verify(VerificationRequest(action="write", actual="bad", check=lambda value: value == "ok"))
    assert result.status == VerificationStatus.FAILED


def test_verification_exception_is_uncertain():
    def broken(_):
        raise RuntimeError("sensor unavailable")

    result = Verifier().verify(VerificationRequest(action="write", actual="ok", check=broken))
    assert result.status == VerificationStatus.UNCERTAIN
    assert "could not be completed" in result.reason


def test_empty_action_is_rejected():
    try:
        Verifier().verify(VerificationRequest(action="", expected=1, actual=1))
    except ValueError as exc:
        assert "action" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_self_correction_retries_with_revised_arguments():
    from core.authorization import IdentityLevel
    from workflow.action_executor import ActionExecutionEngine
    from workflow.action_registry import ActionRegistry, ActionSpec
    from workflow.self_correction import SelfCorrectionEngine

    registry = ActionRegistry()
    state = []

    def write(value):
        state.append(value)
        return value

    registry.register(ActionSpec("write", "write a value", handler=write))
    engine = ActionExecutionEngine(registry)

    corrector = SelfCorrectionEngine(
        engine,
        correction=lambda execution, verification, attempt: {"value": "correct"},
        max_corrections=1,
    )
    result = corrector.execute(
        "write",
        {"value": "wrong"},
        identity=IdentityLevel.OWNER,
        expected="correct",
    )

    assert result.success is True
    assert result.status == "verified"
    assert state == ["wrong", "correct"]
    assert len(result.attempts) == 2


def test_self_correction_does_not_claim_success_without_verification():
    from core.authorization import IdentityLevel
    from workflow.action_executor import ActionExecutionEngine
    from workflow.action_registry import ActionRegistry, ActionSpec
    from workflow.self_correction import SelfCorrectionEngine

    registry = ActionRegistry()
    registry.register(ActionSpec("write", "write a value", handler=lambda value: value))
    engine = ActionExecutionEngine(registry)
    corrector = SelfCorrectionEngine(engine)

    result = corrector.execute("write", {"value": "ok"}, identity=IdentityLevel.OWNER)
    assert result.success is False
    assert result.status == "uncertain"
    assert result.correction_action == "needs_review"


def test_self_correction_respects_approval_gate():
    from core.authorization import IdentityLevel
    from workflow.action_executor import ActionExecutionEngine
    from workflow.action_registry import ActionRegistry, ActionSpec
    from workflow.self_correction import SelfCorrectionEngine

    registry = ActionRegistry()
    registry.register(ActionSpec("delete", "delete data", handler=lambda: "deleted", requires_approval=True))
    engine = ActionExecutionEngine(registry)
    corrector = SelfCorrectionEngine(engine, max_corrections=2)

    result = corrector.execute("delete", identity=IdentityLevel.OWNER, expected="deleted")
    assert result.success is False
    assert result.status == "awaiting_approval"


def test_self_correction_never_carries_approval_to_changed_arguments():
    from core.authorization import IdentityLevel
    from workflow.action_executor import ActionExecutionEngine
    from workflow.action_registry import ActionRegistry, ActionSpec
    from workflow.approval import ApprovalController
    from workflow.self_correction import SelfCorrectionEngine

    registry = ActionRegistry()
    registry.register(ActionSpec("write", "write a value", handler=lambda value: value, requires_approval=True))
    approvals = ApprovalController()
    engine = ActionExecutionEngine(registry, approvals=approvals)
    corrector = SelfCorrectionEngine(
        engine,
        correction=lambda *_: {"value": "correct"},
        max_corrections=1,
    )

    first = engine.execute("write", {"value": "wrong"}, identity=IdentityLevel.OWNER)
    approved = approvals.approve(first.approval_request_id)
    assert approved.status == "approved"

    result = corrector.execute(
        "write",
        {"value": "wrong"},
        identity=IdentityLevel.OWNER,
        approval_request_id=first.approval_request_id,
        expected="correct",
    )
    assert result.success is False
    assert result.status == "awaiting_approval"
