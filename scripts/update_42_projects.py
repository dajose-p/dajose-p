import os
import json
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
README_PATH = os.path.join(BASE_DIR, "README.md")

CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"

AUTH_URL = "https://api.intra.42.fr/oauth/authorize"
TOKEN_URL = "https://api.intra.42.fr/oauth/token"
API_BASE = "https://api.intra.42.fr/v2"

COMMON_CORE_ID = 21
PISCINE_ID = 9

# --- TOKEN MANAGEMENT ---
def save_token(token_data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None

def refresh_token(refresh_token):
    print("♻️ Refreshing access token...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
    )
    if resp.ok:
        token_data = resp.json()
        save_token(token_data)
        return token_data
    else:
        print("❌ Refresh failed:", resp.text)
        return None

# --- OAUTH FLOW ---
class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/callback" in self.path:
            from urllib.parse import urlparse, parse_qs
            code = parse_qs(urlparse(self.path).query).get("code")
            if code:
                self.server.auth_code = code[0]
                self.send_response(200)
                self.end_headers()
                msg = "✅ Code received! You can close this window.".encode("utf-8")
                self.wfile.write(msg)
            else:
                self.send_response(400)
                self.end_headers()

def oauth_flow():
    auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    print("🌐 Starting OAuth flow...")
    webbrowser.open(auth_url)

    httpd = HTTPServer(("localhost", 8080), OAuthHandler)
    httpd.handle_request()
    code = getattr(httpd, "auth_code", None)
    if not code:
        raise Exception("No auth code received.")

    print("🔑 Exchanging code for token...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    save_token(token_data)
    return token_data

def get_access_token():
    token_data = load_token()
    if not token_data:
        print("🪙 No valid token found. Starting OAuth flow...")
        token_data = oauth_flow()

    access_token = token_data.get("access_token")
    refresh = token_data.get("refresh_token")

    # Check if expired
    test = requests.get(f"{API_BASE}/me", headers={"Authorization": f"Bearer {access_token}"})
    if test.status_code == 401 and refresh:
        token_data = refresh_token(refresh)
        access_token = token_data.get("access_token")

    return access_token

# --- API CALLS ---
def get_me():
    token = get_access_token()
    resp = requests.get(f"{API_BASE}/me", headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()

def get_projects():
    token = get_access_token()
    me = get_me()
    login = me.get("login")

    projects = []
    page = 1
    while True:
        resp = requests.get(
            f"{API_BASE}/users/{login}/projects_users?page={page}&per_page=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        projects.extend(data)
        page += 1
    return projects

# --- DATA PROCESSING ---
def categorize_projects(projects):
    cursus_projects = {"done": [], "in_progress": []}
    piscine_projects = {"done": []}

    for p in projects:
        name = p.get("project", {}).get("name", "Unknown Project")
        final_mark = p.get("final_mark")
        validated = p.get("validated?")
        cursus_ids = p.get("cursus_ids", [])
        mark = final_mark if final_mark is not None else "—"

        project_data = {"name": name, "mark": mark, "validated": validated}

        # Common Core
        if COMMON_CORE_ID in cursus_ids:
            if final_mark is not None and final_mark > 0:
                cursus_projects["done"].append(project_data)
            else:
                cursus_projects["in_progress"].append(project_data)

        # Piscine (solo completados y nota >50)
        elif PISCINE_ID in cursus_ids:
            if final_mark is not None and final_mark >= 50:
                piscine_projects["done"].append(project_data)

    return cursus_projects, piscine_projects

# --- HTML GENERATORS ---
def generate_progress_bar(level):
    max_level = 21
    percentage = min(level / max_level * 100, 100)
    return f"""
<div style="width:100%; max-width:500px; margin-bottom:1em; font-family:Arial, sans-serif;">
  <div style="background:#ddd; border-radius:12px; overflow:hidden;">
    <div style="
        width:{percentage:.2f}%;
        background: linear-gradient(90deg, #f39c12, #f1c40f, #2ecc71);
        color:white;
        text-align:center;
        padding:10px 0;
        font-weight:bold;
        transition: width 1s ease-in-out;
    ">
      Level {level:.2f} / {max_level}
    </div>
  </div>
</div>
"""

def generate_project_list(projects):
    if not projects:
        return "<p style='font-style:italic; color:#666;'>No projects yet</p>"

    html = "<div style='display:flex; flex-wrap:wrap; gap:10px;'>\n"
    for p in sorted(projects, key=lambda x: x["name"].lower()):
        color = "#2ecc71" if p["validated"] else "#f1c40f"
        symbol = "✅" if p["validated"] else "🚧"
        html += f"""
<div style='flex:1 1 200px; background:#f9f9f9; border-radius:10px; padding:10px; box-shadow:0 2px 6px rgba(0,0,0,0.1);'>
  <strong>{p['name']}</strong><br>
  <span style='color:{color}; font-weight:bold;'>{symbol} {p['mark']}</span>
</div>
"""
    html += "</div>"
    return html

def replace_section(content, marker, new_html):
    start_marker = f"<!-- {marker} START -->"
    end_marker = f"<!-- {marker} END -->"
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start == -1 or end == -1:
        return content
    return content[: start + len(start_marker)] + "\n" + new_html + "\n" + content[end:]

def update_readme(cursus_projects, piscine_projects, progress_html):
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    readme = replace_section(readme, "PROGRESS", progress_html)

    cursus_html = "<h4>✅ Completed</h4>\n" + generate_project_list(cursus_projects["done"])
    if cursus_projects["in_progress"]:
        cursus_html += "\n<h4>🚧 In Progress</h4>\n" + generate_project_list(cursus_projects["in_progress"])
    readme = replace_section(readme, "CURSUS", cursus_html)

    piscine_html = "<h4>✅ Completed</h4>\n" + generate_project_list(piscine_projects["done"])
    readme = replace_section(readme, "PISCINE", piscine_html)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print("✅ README updated successfully!")

# --- MAIN ---
if __name__ == "__main__":
    print("🔍 Fetching 42 profile and projects...")
    me = get_me()
    level = next((c["level"] for c in me.get("cursus_users", []) if c["cursus_id"] == COMMON_CORE_ID), 0)

    projects = get_projects()
    cursus_projects, piscine_projects = categorize_projects(projects)

    progress_html = generate_progress_bar(level)
    update_readme(cursus_projects, piscine_projects, progress_html)

