from datetime import datetime, timedelta, timezone

import pytest

from workflow.long_running import LongRunningMission, MissionStore


def test_mission_lifecycle_and_checkpoint_persist(tmp_path):
    store = MissionStore(tmp_path)
    mission = LongRunningMission("page-work", "Handle my Facebook page", store=store)

    mission.start()
    mission.checkpoint(progress=35, current_task="Review messages", completed_tasks=["inspect"])
    mission.pause()

    restored = LongRunningMission("page-work", "Handle my Facebook page", store=store)
    assert restored.record.state == "paused"
    assert restored.record.progress == 35
    assert restored.record.checkpoint.current_task == "Review messages"
    assert restored.record.checkpoint.completed_tasks == ["inspect"]
    assert restored.record.checkpoint.sequence >= 3


def test_resume_continues_from_durable_checkpoint(tmp_path):
    store = MissionStore(tmp_path)
    mission = LongRunningMission("research", "Research laptops", store=store)
    mission.start()
    mission.checkpoint(progress=50, current_task="Compare options")
    mission.pause()

    mission = LongRunningMission("research", "Research laptops", store=store)
    mission.resume()
    seen = []

    mission.run_step(lambda checkpoint: seen.append(checkpoint.progress) or {"progress": 75, "current_task": "Recommend one"})

    assert seen == [50]
    assert mission.record.state == "running"
    assert mission.record.progress == 75
    assert mission.record.checkpoint.current_task == "Recommend one"


def test_bounded_step_failure_is_durable(tmp_path):
    store = MissionStore(tmp_path)
    mission = LongRunningMission("unstable", "Do risky work", store=store)
    mission.start()

    result = mission.run_step(lambda _: (_ for _ in ()).throw(RuntimeError("network down")))

    assert result.state == "failed"
    assert result.checkpoint.error == "network down"
    assert MissionStore(tmp_path).load("unstable").state == "failed"


def test_terminal_states_and_cancellation_are_safe(tmp_path):
    store = MissionStore(tmp_path)
    mission = LongRunningMission("cancel-me", "Long task", store=store)
    mission.start()
    mission.cancel()

    assert mission.record.state == "cancelled"
    assert mission.record.completed_at
    assert mission.cancel().state == "cancelled"
    with pytest.raises(RuntimeError):
        mission.start()


def test_complete_sets_progress_to_100(tmp_path):
    mission = LongRunningMission("done", "Finish task", store=MissionStore(tmp_path))
    mission.start()
    result = mission.complete("finished")

    assert result.state == "completed"
    assert result.progress == 100
    assert result.checkpoint.result == "finished"


def test_heartbeat_and_stale_detection(tmp_path):
    store = MissionStore(tmp_path)
    mission = LongRunningMission("heartbeat", "Monitor", store=store)
    mission.start()
    assert mission.record.heartbeat_at
    assert not mission.is_stale(300)

    mission.record.heartbeat_at = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    store.save(mission.record)
    restored = LongRunningMission("heartbeat", "Monitor", store=store)
    assert restored.is_stale(300)


def test_goal_mismatch_cannot_reuse_mission_id(tmp_path):
    store = MissionStore(tmp_path)
    LongRunningMission("same-id", "Original goal", store=store)

    with pytest.raises(ValueError):
        LongRunningMission("same-id", "Different goal", store=store)


def test_store_lists_missions_by_state(tmp_path):
    store = MissionStore(tmp_path)
    first = LongRunningMission("one", "First", store=store)
    first.start()
    second = LongRunningMission("two", "Second", store=store)
    second.start()
    second.pause()

    assert [m.mission_id for m in store.list(states={"paused"})] == ["two"]
    assert {m.mission_id for m in store.list(states={"running"})} == {"one"}
