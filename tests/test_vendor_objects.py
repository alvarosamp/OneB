from scripts.analyze_vendor_objects import analyze


def test_first_seen_not_drawn_time(tmp_path):
    path = tmp_path / 'objects.csv'
    path.write_text('observed_at;name;type;time0;price0;time1;price1;text\n'
                    '2026.04.20 00:00:00;__snapshot__;0;;0;;0;complete\n'
                    '2026.04.20 00:10:00;GFC_1_B_e;100;2026.04.20 00:00:00;100;1970.01.01 00:00:00;0;\n'
                    '2026.04.20 00:20:00;GFC_1_B_e;100;2026.04.20 00:00:00;101;1970.01.01 00:00:00;0;\n', encoding='utf-8')
    report = analyze(path)
    assert report['post_initial_gold_entries'] == 1
    assert report['gold_entry_candidates'][0]['lag_seconds'] == 600
    assert report['field_revisions']['price0'] == 1
