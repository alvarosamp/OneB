from app import calendar_risk


def test_event_names_from_app_feed_map_to_study_types():
    assert calendar_risk.event_type("Consumer Price Index (CPI)") == "CPI"
    assert calendar_risk.event_type("Employment Situation (NFP)") == "NFP"
    assert calendar_risk.event_type("FOMC Press Release") == "FOMC"
    assert calendar_risk.event_type("Personal Income and Outlays (PCE)") == "PCE"
    assert calendar_risk.event_type("Gross Domestic Product (GDP)") == "GDP"
    assert calendar_risk.event_type("Advance Monthly Retail Sales") is None


def test_risk_only_lists_assets_that_passed(tmp_path, monkeypatch):
    import json
    f = tmp_path / "calendar_v1.json"
    nas = {"CPI": {"H1_passed": True, "post30": {"median_ratio": 3.9, "ci95": [2.6, 5.4], "events": 88}, "post5": {"median_ratio": 6.7}}}
    eur = {"CPI": {"H1_passed": False, "post30": {"median_ratio": 1.1, "ci95": [0.9, 1.3], "events": 88}}}
    data = {"test": "calendar_v1", "assets": {"NAS100": {"H1_volatility": nas}, "EURUSD": {"H1_volatility": eur}}}
    f.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(calendar_risk, "SUMMARY", f)
    r = calendar_risk.risk_for("Consumer Price Index (CPI)")
    assert [a["asset"] for a in r["assets"]] == ["NAS100"] and r["assets"][0]["post30"] == 3.9
