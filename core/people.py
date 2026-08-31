"""Persistent people and relationship memory for AI-OS."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PEOPLE_FILE = Path("data/people.json")


@dataclass(frozen=True)
class Person:
    """A person known to JARVIS, independent of future biometric identifiers."""

    name: str
    relationship: str | None = None
    person_id: str | None = None
    notes: tuple[str, ...] = ()


class PeopleMemory:
    """Small persistent registry for names, relationships, and future identities."""

    def __init__(self, path: Path = PEOPLE_FILE):
        self.path = path

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, people: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(people, file, indent=2)

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().casefold()

    def remember(self, person: Person) -> Person:
        if not person.name.strip():
            raise ValueError("Person name cannot be empty")
        people = self._load()
        people[self._key(person.name)] = asdict(person)
        self._save(people)
        return person

    def recall(self, name: str) -> Person | None:
        data = self._load().get(self._key(name))
        if data is None:
            return None
        data["notes"] = tuple(data.get("notes", ()))
        return Person(**data)

    def all(self) -> list[Person]:
        return [self.recall(data["name"]) for data in self._load().values()]


people_memory = PeopleMemory()

__all__ = ["Person", "PeopleMemory", "people_memory"]
