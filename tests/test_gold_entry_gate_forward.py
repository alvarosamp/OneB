import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_gold_entry_gate_forward import verify_config


def test_forward_entry_gate_registration_is_frozen():
    config = json.loads((ROOT / 'configs/gold_entry_gate_forward_v1.json').read_text(encoding='utf-8'))
    verify_config(config)
    changed = dict(config, min_net_reward_to_risk=0.5)
    with pytest.raises(ValueError, match='registered'):
        verify_config(changed)
    changed = dict(config, to_exclusive='2026-05-30')
    with pytest.raises(ValueError, match='registered'):
        verify_config(changed)
    followup = json.loads((ROOT / 'configs/gold_entry_gate_followup_v1.json').read_text(encoding='utf-8'))
    verify_config(followup)
