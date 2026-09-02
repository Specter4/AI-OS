from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.execution_recovery import ExecutionRecovery
from workflow.approval import ApprovalController


def make_engine(handler):
    registry = ActionRegistry()
    registry.register(ActionSpec("test", "test action", handler, metadata={"permission": Permission.READ}))
    return ActionExecutionEngine(registry, approvals=ApprovalController())


def test_success_is_reported_with_attempt_history():
    engine = make_engine(lambda value: value * 2)
    result = ExecutionRecovery(engine).execute("test", {"value": 3}, identity=IdentityLevel.UNKNOWN)
    assert result.success is True
    assert result.status == "completed"
    assert result.output == 6
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "completed"


def test_failed_action_is_not_retried_by_default():
    calls = []
    engine = make_engine(lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("temporary")))
    result = ExecutionRecovery(engine, max_retries=3).execute("test", identity=IdentityLevel.UNKNOWN)
    assert result.success is False
    assert result.status == "failed"
    assert result.error == "temporary"
    assert len(result.attempts) == 1
    assert result.recovery_action == "retry_not_recommended"


def test_retry_policy_can_retry_transient_failure():
    calls = []

    def handler():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("temporary")
        return "ok"

    engine = make_engine(handler)
    recovery = ExecutionRecovery(
        engine,
        max_retries=3,
        retry_policy=lambda result, attempt: result.error == "temporary",
    )
    result = recovery.execute("test", identity=IdentityLevel.UNKNOWN)
    assert result.success is True
    assert result.output == "ok"
    assert len(result.attempts) == 3
    assert calls == [1, 1, 1]


def test_retries_stop_after_max_retries():
    calls = []
    engine = make_engine(lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("down")))
    result = ExecutionRecovery(
        engine,
        max_retries=2,
        retry_policy=lambda result, attempt: True,
    ).execute("test", identity=IdentityLevel.UNKNOWN)
    assert result.success is False
    assert result.status == "failed"
    assert len(result.attempts) == 3
    assert len(calls) == 3


def test_approval_result_is_preserved_without_retry():
    registry = ActionRegistry()
    registry.register(ActionSpec("write", "write action", lambda: "done", metadata={"permission": Permission.WRITE}))
    engine = ActionExecutionEngine(registry, approvals=ApprovalController())
    result = ExecutionRecovery(engine, max_retries=3, retry_policy=lambda *_: True).execute(
        "write", identity=IdentityLevel.OWNER
    )
    assert result.success is False
    assert result.status == "awaiting_approval"
    assert result.approval_request_id is not None
    assert len(result.attempts) == 1
