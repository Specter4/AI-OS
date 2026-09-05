from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.capabilities import CapabilityRegistry, CapabilitySpec
from workflow.tool_selection import AutonomousToolExecutor, ToolSelector


def make_system():
    actions = ActionRegistry()
    capabilities = CapabilityRegistry()
    calls = []

    actions.register(ActionSpec("read_file", "Read a file from the workspace", lambda path: calls.append(("read", path)) or "content", metadata={"permission": Permission.READ.value}))
    actions.register(ActionSpec("write_file", "Write content to a workspace file", lambda path, content: calls.append(("write", path, content)) or "saved", requires_approval=True, metadata={"permission": Permission.WRITE.value}))
    actions.register(ActionSpec("search_web", "Search the web for information", lambda query: calls.append(("search", query)) or "results", metadata={"permission": Permission.READ.value}))
    capabilities.register(CapabilitySpec("Filesystem", "Workspace file operations", "computer", ("read_file", "write_file")))
    capabilities.register(CapabilitySpec("Web Research", "Internet research", "browser", ("search_web",)))
    return actions, capabilities, calls


def test_discover_returns_only_registered_executable_actions():
    actions, capabilities, _ = make_system()
    candidates = ToolSelector(actions, capabilities).discover("search the web")
    assert [item.action for item in candidates] == ["search_web"]


def test_capability_metadata_improves_matching():
    actions, capabilities, _ = make_system()
    selection = ToolSelector(actions, capabilities).select("workspace file")
    assert selection.selected is not None
    assert selection.selected.action in {"read_file", "write_file"}
    assert selection.selected.capability == "Filesystem"


def test_exact_action_name_wins():
    actions, capabilities, _ = make_system()
    selection = ToolSelector(actions, capabilities).select("search web")
    assert selection.selected is not None
    assert selection.selected.action == "search_web"


def test_selection_is_deterministic_for_ties():
    actions = ActionRegistry()
    actions.register(ActionSpec("beta", "read data", lambda: None))
    actions.register(ActionSpec("alpha", "read data", lambda: None))
    selector = ToolSelector(actions)
    assert selector.select("read").selected.action == "alpha"


def test_unexecutable_action_is_not_selected():
    actions = ActionRegistry()
    actions.register(ActionSpec("read_file", "read a file"))
    assert ToolSelector(actions).select("read file").status == "no_match"


def test_no_match_does_not_execute_anything():
    actions, capabilities, calls = make_system()
    engine = ActionExecutionEngine(actions)
    result = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine).execute("make coffee")
    assert result.selection.selected is None
    assert result.execution is None
    assert calls == []


def test_executor_delegates_read_action_to_execution_engine():
    actions, capabilities, calls = make_system()
    engine = ActionExecutionEngine(actions)
    result = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine).execute("read file", {"path": "notes.txt"}, identity=IdentityLevel.OWNER)
    assert result.selection.selected.action == "read_file"
    assert result.execution.success is True
    assert result.execution.output == "content"
    assert calls == [("read", "notes.txt")]


def test_executor_preserves_arguments_and_approval_gate():
    actions, capabilities, calls = make_system()
    engine = ActionExecutionEngine(actions)
    executor = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine)
    first = executor.execute("write file", {"path": "notes.txt", "content": "hello"}, identity=IdentityLevel.OWNER)
    assert first.execution.status == "awaiting_approval"
    assert first.execution.approval_request_id is not None
    assert calls == []


def test_unknown_speaker_cannot_bypass_selected_write_action():
    actions, capabilities, calls = make_system()
    engine = ActionExecutionEngine(actions)
    result = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine).execute("write file", {"path": "notes.txt", "content": "hello"}, identity=IdentityLevel.UNKNOWN)
    assert result.execution.status == "denied"
    assert calls == []


def test_approved_request_executes_exact_arguments():
    actions, capabilities, calls = make_system()
    engine = ActionExecutionEngine(actions)
    executor = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine)
    first = executor.execute("write file", {"path": "notes.txt", "content": "hello"}, identity=IdentityLevel.OWNER)
    request_id = first.execution.approval_request_id
    engine.approvals.approve(request_id)
    second = executor.execute("write file", {"path": "notes.txt", "content": "hello"}, identity=IdentityLevel.OWNER, approval_request_id=request_id)
    assert second.execution.success is True
    assert calls == [("write", "notes.txt", "hello")]


def test_mismatched_approved_arguments_are_rejected():
    actions, capabilities, _ = make_system()
    engine = ActionExecutionEngine(actions)
    executor = AutonomousToolExecutor(ToolSelector(actions, capabilities), engine)
    first = executor.execute("write file", {"path": "notes.txt", "content": "hello"}, identity=IdentityLevel.OWNER)
    request_id = first.execution.approval_request_id
    engine.approvals.approve(request_id)
    second = executor.execute("write file", {"path": "notes.txt", "content": "changed"}, identity=IdentityLevel.OWNER, approval_request_id=request_id)
    assert second.execution.status == "rejected"
