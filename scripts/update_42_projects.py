#!/usr/bin/env python3
import os
import json
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ----------------------------
# CONFIG
# ----------------------------
CLIENT_ID = os.environ.get("FT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FT_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_FILE = "scripts/token.json"
COMMON_CORE_ID = 21  # Ajusta según tu cursus ID

README_FILE = "../README.md"
API_BASE = "https://api.intra.42.fr/v2"

# ----------------------------
# TOKEN HANDLING
# ----------------------------
def save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)

def get_new_token(code):
    resp = requests.post(f"{API_BASE}/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    })
    data = resp.json()
    save_token(data)
    return data["access_token"]

def oauth_flow():
    url = f"https://api.intra.42.fr/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    print("🌐 Opening browser for OAuth...")
    webbrowser.open(url)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            code = query.get("code")
            if code:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write("✅ Code received! You can close this window.".encode("utf-8"))
                self.server.code = code[0]

    server = HTTPServer(("127.0.0.1", 8080), Handler)
    server.handle_request()
    return get_new_token(server.code)

def get_access_token():
    token = load_token()
    if token:
        return token.get("access_token")
    return oauth_flow()

# ----------------------------
# API REQUESTS
# ----------------------------
def get_projects(token):
    projects = []
    page = 1
    while True:
        resp = requests.get(f"{API_BASE}/me/projects_users",
                            headers={"Authorization": f"Bearer {token}"},
                            params={"page": page, "per_page": 50})
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        projects.extend(data)
        page += 1
    return projects

# ----------------------------
# PROCESSING
# ----------------------------
def categorize_projects(projects):
    cursus = []
    piscine = []
    for p in projects:
        mark = p.get("final_mark") or 0
        cursus_ids = [c['cursus_id'] for c in p.get("cursus", [])]
        validated = False
        if COMMON_CORE_ID in cursus_ids:
            if mark > 0:
                validated = True
            cursus.append({"name": p["project"]["name"], "mark": mark, "validated": validated})
        else:
            if mark > 50:
                validated = True
            piscine.append({"name": p["project"]["name"], "mark": mark, "validated": validated})
    # Ordenar proyectos por nombre
    cursus.sort(key=lambda x: x["name"].lower())
    piscine.sort(key=lambda x: x["name"].lower())
    return cursus, piscine

def get_level_progress(cursus_projects):
    done = sum(1 for p in cursus_projects if p["validated"])
    total = len(cursus_projects)
    level = done
    return level, done, total

# ----------------------------
# HTML GENERATORS
# ----------------------------
def generate_progress_bar(level, total):
    percentage = int(level / total * 100) if total else 0
    return f"""
<div style="background:#eee; border-radius:12px; overflow:hidden; width:100%; max-width:500px; margin-bottom:1em;">
  <div style="width:{percentage}%; background:#4CAF50; color:white; text-align:center; padding:8px 0; font-weight:bold;">
    Level {level} / {total} ({percentage}%)
  </div>
</div>
"""

def generate_project_list(projects):
    if not projects:
        return "<p style='font-style:italic; color:#666;'>No projects yet</p>"
    html = "<ul>\n"
    for p in projects:
        symbol = "✅" if p["validated"] else "🚧"
        html += f"<li><strong>{p['name']}</strong> — {symbol} {p['mark']}</li>\n"
    html += "</ul>"
    return html

def replace_section(text, marker, content):
    import re
    pattern = re.compile(f"<!-- {marker} START -->.*?<!-- {marker} END -->", re.DOTALL)
    return pattern.sub(f"<!-- {marker} START -->\n{content}\n<!-- {marker} END -->", text)

def update_readme(cursus, piscine, progress_html):
    with open(README_FILE, "r", encoding="utf-8") as f:
        readme = f.read()
    readme = replace_section(readme, "PROGRESS", progress_html)
    readme = replace_section(readme, "CURSUS", generate_project_list(cursus))
    readme = replace_section(readme, "PISCINE", generate_project_list(piscine))
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(readme)
    print("✅ README.md updated!")

# ----------------------------
# MAIN
# ----------------------------
def main():
    token = get_access_token()
    projects = get_projects(token)
    cursus_projects, piscine_projects = categorize_projects(projects)
    level, done, total = get_level_progress(cursus_projects)
    progress_html = generate_progress_bar(done, total)
    update_readme(cursus_projects, piscine_projects, progress_html)

if __name__ == "__main__":
    main()

