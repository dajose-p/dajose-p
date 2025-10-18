import os
import requests
import re
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import webbrowser
import time

# ---------------------------
# CONFIG
# ---------------------------
CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
CURLUS_ID_COMMON_CORE = 21  # ID del Common Core
TOKEN_FILE = "token.json"
SCOPE = "public"

# Ruta absoluta al README del repo (un nivel arriba de scripts/)
README_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md")

HEADERS = {}

# ---------------------------
# OAuth 2.0 Functions
# ---------------------------
def get_saved_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            if data.get("expires_at", 0) > time.time():
                return data["access_token"]
    return None

def save_token(token_data):
    token_data["expires_at"] = time.time() + token_data["expires_in"] - 10
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)

def refresh_token(refresh_token):
    resp = requests.post(
        "https://api.intra.42.fr/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    )
    resp.raise_for_status()
    token_data = resp.json()
    save_token(token_data)
    return token_data["access_token"]

def get_authorization_code():
    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if "code" in params:
                self.server.auth_code = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write("✅ Code received! You can close this window.".encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write("No code found.".encode("utf-8"))
    
    httpd = HTTPServer(("localhost", 8080), OAuthHandler)
    webbrowser.open(
        f"https://api.intra.42.fr/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={SCOPE}"
    )
    print("🌐 Waiting for OAuth callback in browser...")
    httpd.handle_request()
    return httpd.auth_code

def exchange_code_for_token(code):
    resp = requests.post(
        "https://api.intra.42.fr/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
    )
    resp.raise_for_status()
    token_data = resp.json()
    save_token(token_data)
    return token_data["access_token"]

def get_access_token():
    token = get_saved_token()
    if token:
        return token
    print("No valid token found. Starting OAuth flow...")
    code = get_authorization_code()
    return exchange_code_for_token(code)

# ---------------------------
# 42 API Functions
# ---------------------------
def get_cursus_progress(projects):
    total = sum(1 for pu in projects if CURLUS_ID_COMMON_CORE in pu.get("cursus_ids", []))
    done = sum(1 for pu in projects
               if CURLUS_ID_COMMON_CORE in pu.get("cursus_ids", [])
               and pu.get("final_mark") is not None
               and pu.get("final_mark") > 0)
    progress = int(done / total * 100) if total > 0 else 0
    return progress, done, total

def get_projects():
    resp = requests.get("https://api.intra.42.fr/v2/me", headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("projects_users", [])

def classify_projects(projects):
    cursus_done = []
    piscine_done = []

    for pu in projects:
        try:
            project_name = pu["project"]["name"]
            status = pu.get("status", "unknown")
            mark = pu.get("final_mark")
            cursus_ids = pu.get("cursus_ids", [])
            is_piscine = pu["project"]["slug"].startswith("piscine")

            # Filtrado según nota
            if is_piscine and (mark is None or mark <= 50):
                continue
            if not is_piscine and (mark is None or mark == 0):
                continue

            entry = f"<li><strong>{project_name}</strong> — {'✅' if status=='finished' else '🚧'} ({mark})</li>"

            if is_piscine:
                piscine_done.append(entry)
            else:
                cursus_done.append(entry)

        except Exception:
            continue

    return cursus_done, piscine_done

# ---------------------------
# README Update
# ---------------------------
def update_readme(progress, done, total, cursus, piscine):
    try:
        with open(README_PATH, "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        readme = ""

    # Barra de progreso con número de proyectos
    progress_bar = f"""
<div style="background:#eee; border-radius:10px; overflow:hidden; width:100%; max-width:500px; margin-bottom:1em;">
  <div style="background:#4CAF50; width:{progress}%; color:white; text-align:center; padding:8px 0;">
    {progress}% - {done}/{total} Common Core projects completed
  </div>
</div>
"""

    cursus_html = "<ul>\n" + "\n".join(cursus) + "\n</ul>" if cursus else "<p>No projects yet</p>"
    piscine_html = "<ul>\n" + "\n".join(piscine) + "\n</ul>" if piscine else "<p>No projects yet</p>"

    readme = re.sub(
        r"(<!-- PROGRESS START -->)(.*?)(<!-- PROGRESS END -->)",
        f"\\1\n{progress_bar}\n\\3",
        readme,
        flags=re.DOTALL
    )

    readme = re.sub(
        r"(<!-- CURSUS START -->)(.*?)(<!-- CURSUS END -->)",
        f"\\1\n{cursus_html}\n\\3",
        readme,
        flags=re.DOTALL
    )

    readme = re.sub(
        r"(<!-- PISCINE START -->)(.*?)(<!-- PISCINE END -->)",
        f"\\1\n{piscine_html}\n\\3",
        readme,
        flags=re.DOTALL
    )

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print("✅ README.md updated successfully!")

# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    token = get_access_token()
    HEADERS["Authorization"] = f"Bearer {token}"

    projects = get_projects()
    progress, done, total = get_cursus_progress(projects)
    cursus_projects, piscine_projects = classify_projects(projects)

    print(f"Common Core projects completed: {done}/{total}")
    update_readme(progress, done, total, cursus_projects, piscine_projects)

