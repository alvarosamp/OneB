import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('bidask_audit', Path(__file__).parents[1] / 'scripts/audit_bidask_dataset.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_invalid_and_crossed_quotes_are_not_approved(tmp_path):
    file = tmp_path / 'quotes.csv'
    file.write_text('timestamp,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close\n'
                    '2023-01-03T00:00:00Z,100,99,98,100,99,101,98,100\n', encoding='utf-8')
    report = module.audit(file)
    assert not report['integrity_pass']
    assert report['ohlc_invalid']['bid'] == 1
    assert report['spread']['open']['negative'] == 1


def test_empty_feed_is_not_integrity_pass(tmp_path):
    file = tmp_path / 'empty.csv'
    file.write_text('timestamp,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close\n', encoding='utf-8')
    assert not module.audit(file)['integrity_pass']
