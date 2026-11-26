import json
from pathlib import Path

import pytest

FILES = sorted((Path(__file__).parent.parent / "examples" / "checklists").glob("*.json"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_starter_checklist_shape(path):
    items = json.loads(path.read_text(encoding="utf-8"))
    assert items
    for it in items:
        assert it["label"].strip()
        assert it["item_type"] in {"pass_fail", "numerical", "multi_check"}


def test_both_starters_present():
    assert {p.name for p in FILES} == {"en61439-routine.json", "quid-box.json"}
