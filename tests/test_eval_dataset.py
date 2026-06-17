"""Tests for the quality evaluation dataset."""

from opensuse_ai.eval_dataset import EVAL_ITEMS


def test_eval_dataset_ids_are_unique():
    ids = [item.id for item in EVAL_ITEMS]

    assert len(ids) == len(set(ids))


def test_eval_dataset_covers_common_onboarding_failures():
    ids = {item.id for item in EVAL_ITEMS}

    assert "packman_vendor_change" in ids
    assert "codecs" in ids
    assert "wifi_bluetooth" in ids
    assert "disk_full_snapshots" in ids
    assert "failed_systemd_services" in ids


def test_eval_dataset_items_have_expected_facts():
    assert all(item.query.strip() for item in EVAL_ITEMS)
    assert all(item.reference.strip() for item in EVAL_ITEMS)
    assert all(item.expected_facts for item in EVAL_ITEMS)
