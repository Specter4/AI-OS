from pathlib import Path

import pytest

from core.tool_registry import Permission, registry
from tools.filesystem import FileSystem
import tools.registry  # noqa: F401 - registers built-in tools


def test_absolute_paths_work_inside_configured_roots(tmp_path):
    root = tmp_path / "user"
    root.mkdir()
    fs = FileSystem(root / "workspace", allowed_roots=[root])
    target = root / "Documents" / "notes.txt"

    fs.write_file(target, "from PC")
    assert fs.read_file(target) == "from PC"
    assert fs.get_file_info(target)["type"] == "file"


def test_paths_outside_configured_roots_are_rejected(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("private")

    fs = FileSystem(allowed, allowed_roots=[allowed])
    with pytest.raises(PermissionError):
        fs.read_file(secret)
    with pytest.raises(PermissionError):
        fs.write_file(secret, "no")


def test_write_refuses_overwrite_unless_explicit(tmp_path):
    fs = FileSystem(tmp_path)
    fs.write_file("note.txt", "first")

    with pytest.raises(FileExistsError):
        fs.write_file("note.txt", "second")

    fs.write_file("note.txt", "second", overwrite=True)
    assert fs.read_file("note.txt") == "second"


def test_read_size_limit_and_invalid_arguments(tmp_path):
    # Keep this test workspace-only: the production default intentionally
    # grants access to the signed-in user's home directory.
    fs = FileSystem(tmp_path, allowed_roots=[tmp_path])
    fs.write_file("large.txt", "12345")

    with pytest.raises(ValueError, match="read limit"):
        fs.read_file("large.txt", max_bytes=4)
    with pytest.raises(ValueError):
        fs.read_file("large.txt", max_bytes=0)
    with pytest.raises(PermissionError):
        fs.list_directory("../outside")


def test_search_files_matches_names_and_respects_result_limit(tmp_path):
    fs = FileSystem(tmp_path)
    fs.write_file("a.txt", "a")
    fs.write_file("nested/b.txt", "b")
    fs.write_file("nested/c.md", "c")

    results = fs.search_files("*.txt", max_results=1)
    assert len(results) == 1
    assert results[0]["name"] == "a.txt"
    assert len(fs.search_files("*.txt")) == 2
    assert len(fs.search_files("*.txt", recursive=False)) == 1


def test_copy_move_and_rename_preserve_contents_without_overwrite(tmp_path):
    fs = FileSystem(tmp_path)
    fs.write_file("source.txt", "payload")
    copied = Path(fs.copy_file("source.txt", "copies/source.txt"))
    assert copied.read_text() == "payload"

    with pytest.raises(FileExistsError):
        fs.copy_file("source.txt", "copies/source.txt")

    moved = Path(fs.move_file("source.txt", "moved.txt"))
    assert moved.read_text() == "payload"
    assert not (tmp_path / "source.txt").exists()

    renamed = Path(fs.rename_file("moved.txt", "final.txt"))
    assert renamed.name == "final.txt"
    assert renamed.read_text() == "payload"
    with pytest.raises(FileExistsError):
        fs.rename_file("final.txt", "final.txt")

    with pytest.raises(ValueError, match="different paths"):
        fs.copy_file("final.txt", "final.txt", overwrite=True)
    with pytest.raises(ValueError, match="different paths"):
        fs.move_file("final.txt", "final.txt", overwrite=True)


def test_delete_file_and_directory_are_separate_destructive_operations(tmp_path):
    fs = FileSystem(tmp_path)
    fs.write_file("folder/file.txt", "data")

    with pytest.raises(OSError):
        fs.delete_directory("folder")
    assert fs.delete_file("folder/file.txt")["success"] is True
    assert fs.delete_directory("folder")["success"] is True

    fs.write_file("nested/deeper/file.txt", "data")
    assert fs.delete_directory("nested", recursive=True)["recursive"] is True
    assert not (tmp_path / "nested").exists()


def test_configured_roots_and_workspace_cannot_be_deleted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    workspace = root / "workspace"
    fs = FileSystem(workspace, allowed_roots=[root])
    with pytest.raises(PermissionError):
        fs.delete_directory(workspace)
    with pytest.raises(PermissionError):
        fs.delete_directory(root)


def test_registry_exposes_file_tools_with_correct_permissions():
    descriptions = {item["name"]: item for item in registry.describe()}
    assert descriptions["filesystem.read_file"]["permission"] == Permission.READ.value
    assert descriptions["filesystem.search_files"]["permission"] == Permission.READ.value
    assert descriptions["filesystem.copy_file"]["permission"] == Permission.WRITE.value
    assert descriptions["filesystem.move_file"]["permission"] == Permission.WRITE.value
    assert descriptions["filesystem.rename_file"]["permission"] == Permission.WRITE.value
    assert descriptions["filesystem.delete_file"]["permission"] == Permission.DESTRUCTIVE.value
    assert descriptions["filesystem.delete_directory"]["permission"] == Permission.DESTRUCTIVE.value


def test_registry_requires_destructive_permission_for_deletion(tmp_path):
    fs = FileSystem(tmp_path)
    fs.write_file("important.txt", "keep")
    name = "test.filesystem.delete"
    registry.register(name, "test delete", fs.delete_file, Permission.DESTRUCTIVE)
    try:
        with pytest.raises(PermissionError):
            registry.invoke(name, "important.txt")
        assert (tmp_path / "important.txt").exists()
        result = registry.invoke(
            name,
            "important.txt",
            approved_permissions={Permission.READ, Permission.DESTRUCTIVE},
        )
        assert result["success"] is True
    finally:
        registry.unregister(name)


def test_symlink_cannot_escape_allowed_roots(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    link = allowed / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform")

    fs = FileSystem(allowed, allowed_roots=[allowed])
    with pytest.raises(PermissionError):
        fs.list_directory(link)


def test_binary_files_round_trip_through_base64(tmp_path):
    import base64

    fs = FileSystem(tmp_path)
    payload = bytes([0, 255, 1, 128, 10, 13])
    encoded = base64.b64encode(payload).decode("ascii")

    fs.write_file_base64("image.bin", encoded)
    assert fs.read_file_base64("image.bin") == encoded
    assert (tmp_path / "image.bin").read_bytes() == payload

    with pytest.raises(ValueError, match="valid base64"):
        fs.write_file_base64("invalid.bin", "not base64!")
    with pytest.raises(FileExistsError):
        fs.write_file_base64("image.bin", encoded)
