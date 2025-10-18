import os
import requests
import re
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USERNAME = os.getenv("FT_USERNAME", "danjose-")
ACCESS_TOKEN = os.getenv("FT_ACCESS_TOKEN")

if not ACCESS_TOKEN:
    raise SystemExit("❌ Missing FT_ACCESS_TOKEN environment variable")

API_URL = f"https://api.intra.42.fr/v2/users/{USERNAME}/projects_users"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "User-Agent": "42ProjectsUpdater/1.0 (+https://github.com/dajose-p)"
}

# --- Session with retries ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_projects():
    all_projects = []
    page = 1

    print("🔍 Fetching projects from 42 API...")

    while True:
        try:
            resp = session.get(API_URL, headers=HEADERS, params={"page": page, "per_page": 50}, timeout=10)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed on page {page}: {e}")
            break

        data = resp.json()
        if not data:
            break

        all_projects.extend(data)
        print(f"📄 Page {page} loaded ({len(data)} projects)")
        page += 1
        time.sleep(0.5)  # prevent rate-limit

    print(f"✅ Total projects retrieved: {len(all_projects)}")
    return all_projects


def classify_projects(projects):
    completed, in_progress = [], []

    for pu in projects:
        try:
            project_name = pu["project"]["name"]
            status = pu.get("status", "unknown")
            mark = pu.get("final_mark")
            cursus_ids = pu.get("cursus_ids", [])

            # Skip non-main cursus
            if not cursus_ids or 21 not in cursus_ids:
                continue

            if status == "finished":
                completed.append(f"- **{project_name}** — ✅ ({mark if mark else 'No mark yet'})")
            elif status in ["in_progress", "waiting_for_correction"]:
                in_progress.append(f"- **{project_name}** — 🚧 ({status})")

        except Exception as e:
            print(f"⚠️ Error parsing project: {e}")
            continue

    return completed, in_progress


def update_readme(completed, in_progress):
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        print("❌ README.md not found in repository root.")
        return

    new_completed = "\n".join(completed) if completed else "_No completed projects yet._"
    new_in_progress = "\n".join(in_progress) if in_progress else "_No ongoing projects._"

    readme = re.sub(
        r"(<!-- COMPLETED START -->)(.*?)(<!-- COMPLETED END -->)",
        f"\\1\n{new_completed}\n\\3",
        readme,
        flags=re.DOTALL,
    )
    readme = re.sub(
        r"(<!-- INPROGRESS START -->)(.*?)(<!-- INPROGRESS END -->)",
        f"\\1\n{new_in_progress}\n\\3",
        readme,
        flags=re.DOTALL,
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print("✅ README.md successfully updated.")


if __name__ == "__main__":
    projects = get_projects()
    if not projects:
        raise SystemExit("❌ No data received from API. Check token or username.")
    completed, in_progress = classify_projects(projects)
    update_readme(completed, in_progress)

