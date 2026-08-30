"""简历档案域单测：入档往返、导入幂等、列表轻字段。"""

from pathlib import Path

import pytest

from backend.candidates import archive


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "OBJECTS", tmp_path / "objects")
    monkeypatch.setattr(archive, "ARCHIVE", tmp_path / "archive.jsonl")


def test_save_list_get_roundtrip(isolated: None) -> None:
    result = {"rawText": "abc", "profile": {"skills": []}, "stats": {"totalSkills": 1}}
    record = archive.save_to_archive(b"pdf-bytes", "a.pdf", result)

    assert (archive.OBJECTS / f"{record['resume_id']}.pdf").read_bytes() == b"pdf-bytes"
    rows = archive.list_archive()
    assert len(rows) == 1
    # 列表是轻字段：不含画像与原文
    assert set(rows[0]) == {
        "resume_id",
        "filename",
        "size",
        "suffix",
        "uploaded_at",
        "source",
        "sample_type",
        "parse_mode",
        "parse_error",
        "stats",
    }
    assert rows[0]["sample_type"] == "uploaded"
    detail = archive.get_archive(record["resume_id"])
    assert detail is not None
    assert detail["profile"] == {"skills": []}
    assert detail["raw_text"] == "abc"
    assert archive.get_archive("nope") is None


def test_import_rejects_duplicate_filename(isolated: None, tmp_path: Path) -> None:
    src = tmp_path / "b.pdf"
    src.write_bytes(b"b")
    first = archive.import_file(src)
    assert first["source"] == "imported"
    assert first["stats"] is None
    assert archive.list_archive()[0]["sample_type"] == "controlled"

    with pytest.raises(ValueError, match="已入档"):
        archive.import_file(src)
    assert len(archive.list_archive()) == 1
