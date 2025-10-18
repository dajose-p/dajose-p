import os
import json
import time
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===================== CONFIGURACIÓN =====================
CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_FILE = "token.json"
README_PATH = "../README.md"
API_BASE = "https://api.intra.42.fr/v2"
COMMON_CORE_ID = 21  # ID del cursus 42 Common Core
PISCINE_ID = 9       # ID del cursus Piscine C
# =========================================================


# --------------------- OAUTH ------------------------------
def save_token(token_data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


def get_new_token(auth_code=None):
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code,
    }
    resp = requests.post("https://api.intra.42.fr/oauth/token", data=data)
    resp.raise_for_status()
    token_data = resp.json()
    token_data["created_at"] = time.time()
    save_token(token_data)
    return token_data


def refresh_token(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    resp = requests.post("https://api.intra.42.fr/oauth/token", data=data)
    if resp.status_code == 200:
        token_data = resp.json()
        token_data["created_at"] = time.time()
        save_token(token_data)
        print("🔄 Token renovado correctamente.")
        return token_data
    print(f"⚠️ Error al renovar token: {resp.text}")
    return None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/callback?code="):
            code = self.path.split("code=")[1]
            self.server.auth_code = code
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("✅ Code received! You can close this window.".encode("utf-8"))


def oauth_flow():
    print("🌐 Starting OAuth flow...")
    url = (
        f"https://api.intra.42.fr/oauth/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code"
    )
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8080), OAuthHandler)
    server.handle_request()
    auth_code = getattr(server, "auth_code", None)
    if not auth_code:
        raise Exception("❌ No se pudo obtener el código de autorización.")
    return get_new_token(auth_code)


def get_access_token():
    token = load_token()
    if not token:
        print("🪙 No valid token found. Starting OAuth flow...")
        token = oauth_flow()

    expires_in = token["expires_in"]
    created_at = token.get("created_at", 0)
    if time.time() - created_at >= expires_in - 60:
        print("🔁 Token expirado, renovando...")
        token = refresh_token(token.get("refresh_token")) or oauth_flow()

    return token["access_token"]


# --------------------- API FETCH --------------------------
def get_me():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/me", headers=headers)
    if not resp.ok:
        print(f"⚠️ Error al obtener datos del usuario: {resp.status_code}")
        print(resp.text)
        return None
    return resp.json()


def get_projects():
    me = get_me()
    if not me:
        print("❌ No se pudieron obtener los datos del usuario.")
        return []

    projects = me.get("projects_users", [])
    print(f"✅ Recuperados {len(projects)} proyectos.")
    return projects


# --------------------- PROCESAMIENTO ----------------------
def get_cursus_progress(projects):
    common_core = [
        p for p in projects
        if COMMON_CORE_ID in p.get("cursus_ids", [])
        and p.get("final_mark") is not None
        and p.get("final_mark", 0) > 0
    ]
    done = len(common_core)
    total = len([
        p for p in projects
        if COMMON_CORE_ID in p.get("cursus_ids", [])
    ])
    progress = int((done / total) * 100) if total > 0 else 0
    return progress, done, total


def render_progress_bar(progress, done, total):
    filled = int(progress / 5)
    empty = 20 - filled
    bar = f"<div style='background:#eee;border-radius:10px;overflow:hidden;width:100%;max-width:500px;margin-bottom:1em;'>"
    bar += f"<div style='background:#4CAF50;width:{progress}%;color:white;text-align:center;padding:8px 0;'>"
    bar += f"{progress}% - {done}/{total} Common Core projects completed</div></div>"
    return bar


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
            if final_mark and final_mark > 0:
                cursus_projects["done"].append(project_data)
            else:
                cursus_projects["in_progress"].append(project_data)

        # Piscine (solo completados y con nota > 50)
        elif PISCINE_ID in cursus_ids:
            if final_mark and final_mark > 50:
                piscine_projects["done"].append(project_data)

    return cursus_projects, piscine_projects

def generate_project_list(projects):
    if not projects:
        return "<p>No projects yet</p>"

    # Ordenamos por nombre de proyecto
    projects_sorted = sorted(projects, key=lambda x: x["name"].lower())

    html = ["<ul>"]
    for p in projects_sorted:
        name = p["name"]
        mark = p["mark"]
        emoji = "✅" if p["validated"] else "🟡"
        html.append(f"<li><strong>{name}</strong> — {emoji} ({mark})</li>")
    html.append("</ul>")
    return "\n".join(html)


# --------------------- UPDATE README ----------------------
def update_readme(cursus_projects, piscine_projects, progress_html):
    readme_path = README_PATH

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # Barra de progreso
    readme = replace_section(readme, "PROGRESS", progress_html)

    # --- Cursus ---
    cursus_html = "<h4>✅ Completed</h4>\n" + generate_project_list(cursus_projects["done"])
    if cursus_projects["in_progress"]:
        cursus_html += "\n<h4>🚧 In Progress</h4>\n" + generate_project_list(cursus_projects["in_progress"])
    readme = replace_section(readme, "CURSUS", cursus_html)

    # --- Piscine (solo completados) ---
    piscine_html = "<h4>✅ Completed</h4>\n" + generate_project_list(piscine_projects["done"])
    readme = replace_section(readme, "PISCINE", piscine_html)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)

    print("✅ README updated successfully!")

def replace_section(content, marker, new_html):
    start = f"<!-- {marker} START -->"
    end = f"<!-- {marker} END -->"
    before = content.split(start)[0]
    after = content.split(end)[1]
    return f"{before}{start}\n{new_html}\n{end}{after}"


# --------------------- MAIN -------------------------------
if __name__ == "__main__":
    projects = get_projects()
    cursus_projects, piscine_projects = categorize_projects(projects)
    progress, done, total = get_cursus_progress(projects)
    progress_html = render_progress_bar(progress, done, total)
    update_readme(cursus_projects, piscine_projects, progress_html)

