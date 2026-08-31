from pathlib import Path

from core.people import PeopleMemory, Person


def test_people_memory_remembers_name_and_relationship(tmp_path: Path):
    memory = PeopleMemory(tmp_path / "people.json")
    person = memory.remember(Person(name="Mariam", relationship="mother", person_id="person:mariam"))

    assert memory.recall("mariam") == person
    assert memory.recall(" MARIAM ").relationship == "mother"


def test_people_memory_persists_between_instances(tmp_path: Path):
    path = tmp_path / "people.json"
    PeopleMemory(path).remember(Person(name="Rahim", relationship="friend", notes=("likes football",)))

    restored = PeopleMemory(path).recall("Rahim")
    assert restored is not None
    assert restored.relationship == "friend"
    assert restored.notes == ("likes football",)


def test_unknown_person_returns_none(tmp_path: Path):
    assert PeopleMemory(tmp_path / "people.json").recall("Unknown") is None
