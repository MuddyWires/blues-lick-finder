"""Menu-driven usage report over the agent's Logfire traces.

Run: `uv run python -m reports.report_cli`

The menu and its SQL live in menu.json. SQL must be static text: user input
never goes into a query (the query client has no bind parameters). The only
thing typed here is a trace id, which is validated and used in a URL only.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

BASE = "https://logfire-eu.pydantic.dev"
PROJECT_URL = f"{BASE}/muddy-wires/starter-project/"
MENU_PATH = Path(__file__).parent / "menu.json"

TRACE_ID = re.compile(r"[0-9a-f]{32}")
SERVICE = re.compile(r"[A-Za-z0-9_-]+")
PLACEHOLDER = re.compile(r"\$[A-Za-z_]+")


def load_menu(path=MENU_PATH):
    menu = json.loads(Path(path).read_text())
    if not SERVICE.fullmatch(menu["service"]):
        raise ValueError("invalid service name in menu.json")
    for item in menu["items"]:
        for qry in item.get("queries", []):
            extra = set(PLACEHOLDER.findall(qry["sql"])) - {"$SERVICE"}
            if extra:
                raise ValueError(f"unknown placeholder(s) in menu.json: {extra}")
    return menu


def trace_link(tid):
    tid = tid.strip().lower()
    if not TRACE_ID.fullmatch(tid):
        return None
    return f"{PROJECT_URL}?q=trace_id%3D%27{quote(tid)}%27"


def get_client():
    import dotenv
    from logfire.query_client import LogfireQueryClient

    dotenv.load_dotenv()
    return LogfireQueryClient(read_token=os.environ["LOGFIRE_READ_TOKEN"], base_url=BASE)


def run(item, menu, client):
    if item.get("action") == "trace_link":
        link = trace_link(input("trace id: "))
        print(link or "Not a valid trace id (expected 32 hex characters).")
        return
    since = datetime.now(timezone.utc) - timedelta(days=menu["days"])
    for qry in item["queries"]:
        sql = qry["sql"].replace("$SERVICE", menu["service"])
        rows = client.query_json_rows(sql, min_timestamp=since)["rows"]
        if not rows:
            print("(no data)")
        for row in rows:
            print(qry["row"].format(**row))


def main():
    menu = load_menu()
    client = get_client()
    items = {i["key"]: i for i in menu["items"]}
    while True:
        print("\n" + "\n".join(f"{k}) {i['label']}" for k, i in items.items()) + "\nq) Quit")
        choice = input("> ").strip().lower()
        if choice == "q":
            break
        if choice in items:
            run(items[choice], menu, client)


if __name__ == "__main__":
    main()
