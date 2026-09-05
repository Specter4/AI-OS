from __future__ import annotations

from pathlib import Path

from agents.memory import MemoryStore
from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.control_loop import ControlLoopInput, ControlLoopState, JarvisControlLoop
from workflow.long_running import MissionStore


def make_loop(tmp_path: Path, handler, *, permission=Permission.READ, metadata=None):
    actions = ActionRegistry()
    actions.register(
        ActionSpec(
            "read_value",
            "read a value",
            handler,
            metadata={"permission": permission, **(metadata or {})},
        )
    )
    return JarvisControlLoop(
        actions,
        mission_store=MissionStore(tmp_path / "missions"),
        memory=MemoryStore(tmp_path / "memory.db"),
    )


def test_safe_action_runs_and_is_verified(tmp_path):
    loop = make_loop(tmp_path, lambda: "ready")

    result = loop.run(
        ControlLoopInput(
            "read value",
            identity=IdentityLevel.OWNER,
            expected="ready",
        )
    )

    assert result.state is ControlLoopState.COMPLETED
    assert result.execution is not None and result.execution.success
    assert result.verification is not None and result.verification.verified
    assert result.owner_needs_to_know is False


def test_execution_without_postcondition_is_explicitly_unverified(tmp_path):
    loop = make_loop(tmp_path, lambda: "ready")

    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.OWNER))

    assert result.state is ControlLoopState.COMPLETED_UNVERIFIED
    assert result.owner_needs_to_know is True
    assert result.verification is not None


def test_unknown_speaker_cannot_bypass_elevated_action(tmp_path):
    loop = make_loop(tmp_path, lambda: "changed", permission=Permission.WRITE)

    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.UNKNOWN))

    assert result.state is ControlLoopState.STOPPED
    assert result.judgment is not None
    assert result.execution is None


def test_owner_elevated_action_waits_for_approval(tmp_path):
    loop = make_loop(tmp_path, lambda: "changed", permission=Permission.WRITE)

    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.OWNER))

    assert result.state is ControlLoopState.AWAITING_APPROVAL
    assert result.execution is not None
    assert result.execution.status == "awaiting_approval"


def test_approved_elevated_action_executes_with_exact_arguments(tmp_path):
    seen = []
    loop = make_loop(tmp_path, lambda value: seen.append(value) or value, permission=Permission.WRITE)

    first = loop.run(
        ControlLoopInput(
            "read value",
            arguments={"value": "approved"},
            identity=IdentityLevel.OWNER,
            expected="approved",
            explicit_owner_direction=True,
        )
    )
    request_id = first.execution.approval_request_id
    assert request_id

    from workflow.approval import approval_controller
    approval_controller.approve(request_id)

    second = loop.run(
        ControlLoopInput(
            "read value",
            arguments={"value": "approved"},
            identity=IdentityLevel.OWNER,
            expected="approved",
            explicit_owner_direction=True,
            approval_request_id=request_id,
        )
    )

    assert second.state is ControlLoopState.COMPLETED
    assert seen == ["approved"]


def test_judgment_stop_prevents_execution(tmp_path):
    calls = []
    loop = make_loop(tmp_path, lambda: calls.append(True) or "bad", metadata={"clearly_harmful": True})

    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.OWNER))

    assert result.state is ControlLoopState.STOPPED
    assert calls == []


def test_uncertain_context_asks_before_execution(tmp_path):
    calls = []
    loop = make_loop(tmp_path, lambda: calls.append(True) or "value")

    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.OWNER, uncertain=True))

    assert result.state is ControlLoopState.ASKING
    assert calls == []


def test_external_side_effect_is_disclosed_after_verified_execution(tmp_path):
    loop = make_loop(tmp_path, lambda: "sent", metadata={"external_side_effect": True})

    result = loop.run(
        ControlLoopInput("read value", identity=IdentityLevel.OWNER, expected="sent")
    )

    assert result.state is ControlLoopState.COMPLETED
    assert result.owner_needs_to_know is True
    assert result.judgment is not None
    assert result.judgment.action.value == "inform"


def test_bounded_self_correction_retries_with_new_arguments(tmp_path):
    calls = []
    loop = make_loop(tmp_path, lambda value: calls.append(value) or value)

    def correct(_execution, _verification, _attempt):
        return {"value": "right"}

    result = loop.run(
        ControlLoopInput(
            "read value",
            arguments={"value": "wrong"},
            identity=IdentityLevel.OWNER,
            expected="right",
            correction=correct,
            max_corrections=1,
        )
    )

    assert result.state is ControlLoopState.COMPLETED
    assert result.execution is not None and result.execution.success
    assert calls == ["wrong", "right"]
    assert len(result.execution.attempts) == 2


def test_interruption_pauses_before_execution(tmp_path):
    loop = make_loop(tmp_path, lambda: "never")
    interrupted = lambda: True

    loop.interrupt = interrupted
    result = loop.run(ControlLoopInput("read value", identity=IdentityLevel.OWNER))

    assert result.state is ControlLoopState.PAUSED
    assert result.execution is None


def test_memory_updates_are_explicit_and_durable(tmp_path):
    memory = MemoryStore(tmp_path / "memory.db")
    actions = ActionRegistry()
    actions.register(ActionSpec("read_value", "read a value", lambda: "ok"))
    loop = JarvisControlLoop(
        actions,
        mission_store=MissionStore(tmp_path / "missions"),
        memory=memory,
    )

    result = loop.run(
        ControlLoopInput(
            "read value",
            identity=IdentityLevel.OWNER,
            expected="ok",
            memory_updates=(("last_status", "ok", "context"),),
        )
    )

    assert result.memory_written == ("last_status",)
    assert memory.recall("last_status", category="context").value == "ok"


def test_mission_checkpoint_is_updated_without_bypassing_execution(tmp_path):
    mission_store = MissionStore(tmp_path / "missions")
    actions = ActionRegistry()
    actions.register(ActionSpec("read_value", "read a value", lambda: "ok"))
    loop = JarvisControlLoop(actions, mission_store=mission_store, memory=MemoryStore(tmp_path / "memory.db"))

    result = loop.run(
        ControlLoopInput(
            "read value",
            identity=IdentityLevel.OWNER,
            expected="ok",
            mission_id="mission-1",
        )
    )

    record = mission_store.load("mission-1")
    assert result.state is ControlLoopState.COMPLETED
    assert record.goal == "read value"
    assert record.state == "completed"
    assert record.checkpoint.progress == 100
