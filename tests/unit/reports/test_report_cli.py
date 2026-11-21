import json

import pytest

from reports.report_cli import MENU_PATH, load_menu, trace_link


def test_shipped_menu_loads():
    menu = load_menu()
    assert menu["items"]


def test_service_name_injection_rejected(tmp_path):
    menu = json.loads(MENU_PATH.read_text())
    menu["service"] = "x' or '1'='1"
    path = tmp_path / "menu.json"
    path.write_text(json.dumps(menu))
    with pytest.raises(ValueError):
        load_menu(path)


def test_unknown_placeholder_rejected(tmp_path):
    menu = json.loads(MENU_PATH.read_text())
    menu["items"][0]["queries"][0]["sql"] += " and x = '$USER_INPUT'"
    path = tmp_path / "menu.json"
    path.write_text(json.dumps(menu))
    with pytest.raises(ValueError):
        load_menu(path)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "abc",
        "01a1ede514080767a22947d7c9a7b4a4' or '1'='1",
        "g" * 32,
        "01a1ede514080767a22947d7c9a7b4a4a",
    ],
)
def test_bad_trace_ids_rejected(bad):
    assert trace_link(bad) is None


def test_good_trace_id_gives_link():
    tid = "01a1ede514080767a22947d7c9a7b4a4"
    assert trace_link(f" {tid.upper()} ").endswith(f"%27{tid}%27")
