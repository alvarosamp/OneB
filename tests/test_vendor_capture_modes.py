import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('capture_modes', Path(__file__).parents[1] / 'scripts/compare_vendor_capture_modes.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_price_disagreement_is_not_hidden_by_equal_counts(tmp_path):
    header = 'observed_at;name;price0;price1;text\n'
    left, right = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.write_text(header + 't;entry;100;0;OPEN\n', encoding='utf-8')
    right.write_text(header + 't;entry;101;0;OPEN\n', encoding='utf-8')
    result = module.compare(left, right)
    assert result['only_left'] == result['only_right'] == 0
    assert result['different_common_rows'] == 1
    assert result['changed_fields']['price0'] == 1
    assert result['maximum_absolute_price_difference']['price0'] == 1
