import json
from pathlib import Path
from uuid import uuid4

from app.research_provenance import write_manifest


def test_manifest_hashes_output_and_records_gate(monkeypatch):
    workspace_tmp = (Path("tmp") / "research_provenance_tests" / uuid4().hex).resolve()
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(workspace_tmp)
    artifact = workspace_tmp / "result.json"
    artifact.write_text('{"ok": true}', encoding="utf-8")
    source = workspace_tmp / "source.py"
    source.write_text("print('research')", encoding="utf-8")

    manifest_path = write_manifest(
        artifact,
        command="python -m scripts.example",
        parameters={"seed": 7},
        input_paths=[source],
        data_gate={"status": "PASS"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["output"]["sha256"]
    assert manifest["inputs"][0]["sha256"]
    assert manifest["data_gate"]["status"] == "PASS"
    assert manifest["parameters"] == {"seed": 7}
