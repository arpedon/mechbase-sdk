"""Offline tests for comments, documents and alarm rules (SDK + CLI)."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import Mechbase
from mechbase.cli import main

BASE = "https://example.test"
I = f"{BASE}/api/installations/2044"
COMMENT = {"id": 7, "body": "<div>Noise &amp; heat</div>", "body_text": "Noise & heat", "author_name": "Ann",
           "created_at": "2026-11-26T08:00:00Z", "edited_at": None,
           "references": [{"point_id": 2, "point_sequence": 766}], "is_finding": False, "editable": True}
DOC = {"uuid": "d-1", "name": "manual.pdf", "kind": "manual", "url": "https://x/m.pdf", "created_at": "2026-11-26T08:00:00Z"}
RULE = {"uuid": "r-1", "scope": "point", "method": "threshold", "data_key": "", "effective_data_key": "rms",
        "direction": "high", "minor_threshold": 2.8, "major_threshold": 7.1, "threshold_mode": "absolute", "source": None}
DEFAULT = {**RULE, "uuid": "r-0", "scope": "installation", "source": "iso_10816"}


@pytest.fixture
def inst():
    c = Mechbase(token="tok", base_url=BASE)
    yield c.for_installation(2044)
    c.close()


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    for k, v in {"XDG_CONFIG_HOME": str(tmp_path), "MECHBASE_TOKEN": "tok", "MECHBASE_URL": BASE,
                 "MECHBASE_INSTALLATION": "2044"}.items():
        monkeypatch.setenv(k, v)


@respx.mock
def test_comments_round_trip(inst):
    respx.get(f"{I}/assets/1/comments").mock(return_value=httpx.Response(200, json={"items": [COMMENT], "total": 1, "limit": 50, "offset": 0}))
    post = respx.post(f"{I}/assets/1/comments").mock(return_value=httpx.Response(201, json=COMMENT))
    patch = respx.patch(f"{I}/assets/1/comments/7").mock(return_value=httpx.Response(200, json=COMMENT))
    delete = respx.delete(f"{I}/assets/1/comments/7").mock(return_value=httpx.Response(204))
    assert inst.comments.list(1)[0]["body_text"] == "Noise & heat"
    inst.comments.create(1, "<div>x</div>", references=[{"point_id": 2, "point_sequence": None}])
    assert json.loads(post.calls.last.request.content) == {"body": "<div>x</div>", "references": [{"point_id": 2}]}
    inst.comments.update(1, 7, "<div>y</div>")
    assert json.loads(patch.calls.last.request.content) == {"body": "<div>y</div>", "references": []}
    inst.comments.delete(1, 7)
    assert delete.called


@respx.mock
def test_documents_round_trip(inst):
    respx.get(f"{I}/assets/1/documents").mock(return_value=httpx.Response(200, json=[DOC]))
    up = respx.post(f"{I}/assets/1/documents").mock(return_value=httpx.Response(201, json=DOC))
    rm = respx.delete(f"{I}/assets/1/documents/d-1").mock(return_value=httpx.Response(204))
    assert inst.documents.list(1)[0]["kind"] == "manual"
    inst.documents.add(1, b"%PDF", kind="manual", uuid="d-1")
    body = up.calls.last.request.content
    assert b'name="kind"\r\n\r\nmanual' in body and b'filename="document.pdf"' in body
    inst.documents.delete(1, "d-1")
    assert rm.called


@respx.mock
def test_alarm_rules_round_trip(inst):
    respx.get(f"{I}/measurement-points/2/alarm-rules").mock(return_value=httpx.Response(200, json=[RULE, DEFAULT]))
    post = respx.post(f"{I}/measurement-points/2/alarm-rules").mock(return_value=httpx.Response(201, json=RULE))
    patch = respx.patch(f"{I}/measurement-points/2/alarm-rules/r-1").mock(return_value=httpx.Response(200, json=RULE))
    assert [r["scope"] for r in inst.alarm_rules.list(2)] == ["point", "installation"]
    inst.alarm_rules.create(2, minor_threshold=2.8, major_threshold=7.1)
    assert json.loads(post.calls.last.request.content) == {
        "method": "threshold", "data_key": "", "direction": "high", "minor_threshold": 2.8, "major_threshold": 7.1}
    inst.alarm_rules.update(2, "r-1", major_threshold=6.0)
    assert json.loads(patch.calls.last.request.content) == {"major_threshold": 6.0}


@respx.mock
def test_cli_comment_escapes_and_alarm_set_updates_own_rule(cli_env, capsys):
    post = respx.post(f"{I}/assets/1/comments").mock(return_value=httpx.Response(201, json=COMMENT))
    main(["comment", "add", "1", "<b>hot</b> & loud", "--point", "2", "--reading", "766"])
    sent = json.loads(post.calls.last.request.content)
    assert sent == {"body": "<div>&lt;b&gt;hot&lt;/b&gt; &amp; loud</div>", "references": [{"point_id": 2, "point_sequence": 766}]}

    respx.get(f"{I}/measurement-points/2/alarm-rules").mock(return_value=httpx.Response(200, json=[RULE, DEFAULT]))
    patch = respx.patch(f"{I}/measurement-points/2/alarm-rules/r-1").mock(return_value=httpx.Response(200, json=RULE))
    main(["alarm", "set", "2", "--major", "7.1"])
    assert json.loads(patch.calls.last.request.content) == {"major_threshold": 7.1}
    assert "minor 2.8 · major 7.1" in capsys.readouterr().out

    main(["alarms", "2"])
    assert "iso_10816" in capsys.readouterr().out
