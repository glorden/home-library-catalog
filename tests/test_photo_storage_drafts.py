import os
import time

import pytest

from app.services import photo_storage

DRAFT_A = "a" * 32
DRAFT_B = "b" * 32


def test_sweep_abandoned_drafts_removes_old_and_keeps_fresh():
    old_dir = photo_storage.draft_dir(DRAFT_A)
    fresh_dir = photo_storage.draft_dir(DRAFT_B)
    old_dir.mkdir(parents=True)
    fresh_dir.mkdir(parents=True)
    (old_dir / "cover.jpg").write_bytes(b"x")
    (fresh_dir / "cover.jpg").write_bytes(b"x")

    old_time = time.time() - 49 * 3600
    os.utime(old_dir, (old_time, old_time))

    removed = photo_storage.sweep_abandoned_drafts()

    assert removed == 1
    assert not old_dir.exists()
    assert fresh_dir.exists()


def test_sweep_abandoned_drafts_on_missing_root_returns_zero():
    assert photo_storage.sweep_abandoned_drafts() == 0


@pytest.mark.parametrize("bad_draft_id", ["..", "../../etc", "not-hex", "a" * 31, "a" * 33])
def test_draft_dir_rejects_malformed_draft_id(bad_draft_id):
    with pytest.raises(photo_storage.InvalidDraftIdError):
        photo_storage.draft_dir(bad_draft_id)


def test_resolve_draft_path_rejects_unknown_kind():
    with pytest.raises(photo_storage.InvalidDraftIdError):
        photo_storage.resolve_draft_path(DRAFT_A, "not_a_real_kind")
