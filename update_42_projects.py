import os
import requests
import re

USERNAME = os.getenv("FT_USERNAME", "danjose-")  # your 42 username
ACCESS_TOKEN = os.getenv("FT_ACCESS_TOKEN")

API_URL = f"https://api.intra.42.fr/v2/users/{USERNAME}/projects_users"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

def get_projects():
    all_projects = []
    page = 1

    while True:
        resp = requests.get(API_URL, headers=HEADERS, params={"page": page, "per_page": 50})
        data = resp.json()
        if not data:
            break
        all_projects.extend(data)
        page += 1

    completed, in_progress = [], []

    for pu in all_projects:
        project = pu["project"]["name"]
        status = pu["status"]
        mark = pu.get("final_mark")
        cursus = pu.get("cursus_ids", [])
        if not cursus or 21 not in cursus:  # Filter out Piscine or other cursus
            continue

        if status == "finished":
            completed.append(f"- **{project}** — ✅ ({mark if mark else 'No mark yet'})")
        elif status in ["in_progress", "waiting_for_correction"]:
            in_progress.append(f"- **{project}** — 🚧 ({status})")

    return completed, in_progress


def update_readme(completed, in_progress):
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

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


if __name__ == "__main__":
    completed, in_progress = get_projects()
    update_readme(completed, in_progress)

