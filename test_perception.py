from datetime import datetime, timedelta, timezone

import pytest

from workflow.perception import EnvironmentAwareness, EnvironmentSnapshot, Observation


def obs(kind="screen", value="idle", confidence=1.0, seconds=0):
    return Observation(
        source="test",
        kind=kind,
        value=value,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=seconds),
    )


def test_observation_validates_source_kind_confidence_and_timestamp():
    with pytest.raises(ValueError):
        Observation("", "screen", "x")
    with pytest.raises(ValueError):
        Observation("test", "", "x")
    with pytest.raises(ValueError):
        Observation("test", "screen", "x", confidence=1.1)
    with pytest.raises(ValueError):
        Observation("test", "screen", "x", timestamp=datetime.now())


def test_snapshot_latest_is_case_insensitive():
    first = obs("Screen", "old", seconds=0)
    second = obs("screen", "new", seconds=1)
    snapshot = EnvironmentSnapshot((first, second))
    assert snapshot.latest("SCREEN").value == "new"


def test_snapshot_filters_by_source():
    a = obs("screen", "a")
    b = Observation("camera", "face", "asif", timestamp=a.timestamp)
    snapshot = EnvironmentSnapshot((a, b))
    assert snapshot.by_source("CAMERA")[0].value == "asif"


def test_awareness_ingests_and_limits_history():
    awareness = EnvironmentAwareness(history_limit=2)
    awareness.ingest((obs("screen", "one", seconds=0), obs("screen", "two", seconds=1)))
    snapshot = awareness.ingest((obs("screen", "three", seconds=2),))
    assert [item.value for item in snapshot.observations] == ["two", "three"]


def test_awareness_observe_uses_provider():
    class Provider:
        def observe(self):
            return [obs("camera", "person")]

    awareness = EnvironmentAwareness()
    snapshot = awareness.observe(Provider())
    assert snapshot.latest("camera").value == "person"


def test_changed_since_returns_only_new_observations_and_can_filter_kind():
    baseline = datetime.now(timezone.utc)
    old = Observation("test", "screen", "old", timestamp=baseline - timedelta(seconds=1))
    new_screen = Observation("test", "screen", "new", timestamp=baseline + timedelta(seconds=1))
    new_audio = Observation("test", "audio", "speech", timestamp=baseline + timedelta(seconds=2))
    awareness = EnvironmentAwareness()
    awareness.ingest((old, new_screen, new_audio))
    assert awareness.changed_since(baseline) == (new_screen, new_audio)
    assert awareness.changed_since(baseline, kind="SCREEN") == (new_screen,)


def test_changed_since_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError):
        EnvironmentAwareness().changed_since(datetime.now())


def test_clear_removes_observation_history():
    awareness = EnvironmentAwareness()
    awareness.ingest((obs(),))
    awareness.clear()
    assert awareness.snapshot().observations == ()
