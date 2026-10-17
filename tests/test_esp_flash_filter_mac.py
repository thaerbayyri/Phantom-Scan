import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("esp_flash", ROOT / "firmware" / "esp32-csi-node" / "esp-flash.py")
esp_flash = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(esp_flash)


def _args(**overrides):
    base = dict(
        ssid=None, password=None, target_ip=None, target_port=None, node_id=None,
        tdm_slot=None, tdm_total=None, edge_tier=None, pres_thresh=None,
        fall_thresh=None, vital_win=None, vital_int=None, subk_count=None,
        filter_mac=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_parse_filter_mac_normalizes_separators_and_case():
    assert esp_flash.parse_filter_mac("24:0A:C4:11:22:33") == "240ac4112233"
    assert esp_flash.parse_filter_mac("24-0a-c4-11-22-33") == "240ac4112233"


def test_parse_filter_mac_off_is_the_broadcast_marker():
    assert esp_flash.parse_filter_mac("OFF") == "ffffffffffff"


@pytest.mark.parametrize("bad", ["24:0A:C4:11:22", "zz:0a:c4:11:22:33", "00:00:00:00:00:00", ""])
def test_parse_filter_mac_rejects_invalid_values(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        esp_flash.parse_filter_mac(bad)


def test_nvs_csv_includes_filter_mac_blob_only_when_given():
    with_mac = esp_flash.build_nvs_csv(_args(node_id=3, filter_mac="240ac4112233"))
    assert "filter_mac,data,hex2bin,240ac4112233" in with_mac
    without = esp_flash.build_nvs_csv(_args(node_id=3))
    assert "filter_mac" not in without
