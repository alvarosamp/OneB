import pytest

from scripts.analyze_vendor_signal_audit import analyze


def test_detects_late_signal_and_value_revision(tmp_path):
    path = tmp_path / "buffers.csv"
    path.write_text(
        "observed_at;bar_time;shift;buffer;status;value;error\n"
        "2026.04.15 10:10:00;2026.04.15 10:00:00;1;0;empty;;0\n"
        "2026.04.15 10:20:00;2026.04.15 10:00:00;2;0;ok;100;0\n"
        "2026.04.15 10:30:00;2026.04.15 10:00:00;3;0;ok;101;0\n",
        encoding="utf-8",
    )
    report = analyze(path)
    assert report["rechecks"] == 2
    assert report["closed_bar_buffer_changes"] == 2


def test_refuses_forming_bar(tmp_path):
    path = tmp_path / "buffers.csv"
    path.write_text(
        "observed_at;bar_time;shift;buffer;status;value;error\n"
        "2026.04.15 10:00:00;2026.04.15 10:00:00;0;0;ok;100;0\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        analyze(path)
