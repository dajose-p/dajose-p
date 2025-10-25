import os
import json
import requests
# Se eliminó 'webbrowser' y las librerías del servidor HTTP
# from http.server import HTTPServer, BaseHTTPRequestHandler 

# --- CONFIG ---
# Ajusta la ruta de BASE_DIR si es necesario.
# BASE_DIR apunta a la carpeta inmediatamente superior a donde se ejecuta el script.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
README_PATH = os.path.join(BASE_DIR, "README.md")

# Las variables de entorno FT_CLIENT_ID y FT_CLIENT_SECRET son leídas por el OS
CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
# REDIRECT_URI ya no es necesario

AUTH_URL = "https://api.intra.42.fr/oauth/authorize"
TOKEN_URL = "https://api.intra.42.fr/oauth/token"
API_BASE = "https://api.intra.42.fr/v2"

COMMON_CORE_ID = 21
PISCINE_ID = 9

# --- TOKEN MANAGEMENT ---
def save_token(token_data):
    # Asegura que el archivo token.json se guarde un nivel arriba si el script se ejecuta en una subcarpeta.
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None

# La función refresh_token no es estrictamente necesaria en Client Credentials,
# pero se mantiene por si el token fuese de otro tipo o la API lo soportase.
def refresh_token(refresh_token):
    print("♻️ Refrescando access token...")
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

# --- CLIENT CREDENTIALS FLOW (Flujo automatizado) ---
def get_client_credentials_token():
    """Obtiene un nuevo token de acceso usando Client Credentials Flow."""
    print("🔑 Obteniendo token usando Client Credentials Flow...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "public" # Scope requerido para acceso general
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    save_token(token_data)
    return token_data

def get_access_token():
    token_data = load_token()
    access_token = token_data.get("access_token") if token_data else None

    # 1. Si no hay token guardado, obtiene uno nuevo (Client Credentials Flow)
    if not token_data or not access_token:
        print("🪙 No se encontró token. Iniciando Client Credentials Flow...")
        token_data = get_client_credentials_token()
        return token_data.get("access_token")

    # 2. Si hay token, comprueba si es válido probando un endpoint simple
    test = requests.get(f"{API_BASE}/me", headers={"Authorization": f"Bearer {access_token}"})
    
    # 3. Si el token expiró (código 401), obtenemos uno nuevo (Client Credentials)
    if test.status_code == 401:
        print("❌ Token expirado. Obteniendo un nuevo token (Client Credentials).")
        # Para Client Credentials, si expira, simplemente obtenemos uno nuevo.
        # Se IGNORA refresh_token de la data anterior.
        token_data = get_client_credentials_token()
        access_token = token_data.get("access_token")

    return access_token

# --- API CALLS (El resto del código se mantiene igual) ---
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

        # Piscine (solo completados y nota >=50)
        elif PISCINE_ID in cursus_ids:
            if final_mark is not None and final_mark >= 50:
                piscine_projects["done"].append(project_data)

    return cursus_projects, piscine_projects

# --- HTML GENERATORS ---
def generate_project_list(projects):
    if not projects:
        return "<p style='font-style:italic; color:#666;'>No projects yet</p>"

    html = "<div style='display:flex; flex-direction:column; gap:6px;'>\n"
    for p in sorted(projects, key=lambda x: x["name"].lower()):
        # Se ajusta el formato para la salida Markdown/HTML dentro del README
        mark_display = f"({p['mark']})" if p['mark'] != '—' else ''
        symbol = "✅" if p["validated"] else "🚧"
        html += f"- {p['name']} {symbol} {mark_display}<br>\n"
    html += "</div>"
    return html

def replace_section(content, marker, new_html):
    start_marker = f""
    end_marker = f""
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start == -1 or end == -1:
        # Imprime una advertencia si no encuentra los marcadores
        print(f"⚠️ Warning: Markers '{start_marker}' or '{end_marker}' not found in README.")
        return content
    return content[: start + len(start_marker)] + "\n" + new_html + "\n" + content[end:]

def update_readme(cursus_projects, piscine_projects):
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    # Sección CURSUS
    cursus_html = "<h4>✅ Completed</h4>\n" + generate_project_list(cursus_projects["done"])
    if cursus_projects["in_progress"]:
        cursus_html += "\n<h4>🚧 In Progress</h4>\n" + generate_project_list(cursus_projects["in_progress"])
    readme = replace_section(readme, "CURSUS", cursus_html)

    # Sección PISCINE
    piscine_html = "<h4>✅ Completed</h4>\n" + generate_project_list(piscine_projects["done"])
    readme = replace_section(readme, "PISCINE", piscine_html)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print("✅ README updated successfully!")

# --- MAIN ---
if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Error: FT_CLIENT_ID o FT_CLIENT_SECRET no están configurados como variables de entorno.")
        exit(1)
        
    print("🔍 Fetching 42 profile and projects...")
    try:
        projects = get_projects()
        cursus_projects, piscine_projects = categorize_projects(projects)
        update_readme(cursus_projects, piscine_projects)
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP al llamar a la API: {e}")
        print("Asegúrate que tu CLIENT_ID y CLIENT_SECRET son correctos.")
        exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        exit(1)
