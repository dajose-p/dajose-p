import os
import json
import requests

# --- CONFIG ---
# BASE_DIR apunta a la raíz del repo (si el script se ejecuta desde la raíz o desde .github/workflows)
# Ajustamos para que funcione bien en GitHub Actions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
README_PATH = os.path.join(BASE_DIR, "../README.md")

# Lee las variables de entorno configuradas en GitHub Actions
CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
FT_42_LOGIN = os.getenv("FT_42_LOGIN")

TOKEN_URL = "https://api.intra.42.fr/oauth/token"
API_BASE = "https://api.intra.42.fr/v2"

COMMON_CORE_ID = 21
PISCINE_ID = 9

# --- TOKEN MANAGEMENT ---
def save_token(token_data):
    """Guarda el token de acceso en un archivo local (excluido por .gitignore)."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)

def load_token():
    """Carga el token guardado."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
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
            "scope": "public" 
        },
    )
    resp.raise_for_status() # Lanza error si no es 2xx (ej: 401 si las credenciales son malas)
    token_data = resp.json()
    save_token(token_data)
    return token_data

def get_access_token():
    """Carga o genera un token de acceso válido."""
    token_data = load_token()
    access_token = token_data.get("access_token") if token_data else None

    # 1. Si no hay token guardado, obtiene uno nuevo
    if not token_data or not access_token:
        print("🪙 No se encontró token. Iniciando Client Credentials Flow...")
        token_data = get_client_credentials_token()
        return token_data.get("access_token")

    # 2. Comprueba si el token existente es válido (usando un endpoint simple y público: /cursus)
    # Ya no usamos /me porque falla con Client Credentials.
    test = requests.get(f"{API_BASE}/cursus", headers={"Authorization": f"Bearer {access_token}"})
    
    # 3. Si el token expiró (código 401), obtenemos uno nuevo
    if test.status_code == 401:
        print("❌ Token expirado. Obteniendo un nuevo token (Client Credentials).")
        token_data = get_client_credentials_token()
        access_token = token_data.get("access_token")

    return access_token

# --- API CALLS ---
# Se eliminó la función get_me()

def get_projects():
    """Obtiene todos los proyectos del usuario especificado por FT_42_LOGIN."""
    if not FT_42_LOGIN:
        raise Exception("FT_42_LOGIN no está configurado. No se puede buscar el perfil.")
        
    token = get_access_token()
    login = FT_42_LOGIN 

    projects = []
    page = 1
    while True:
        resp = requests.get(
            f"{API_BASE}/users/{login}/projects_users?page={page}&per_page=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status() # Lanza una excepción por errores HTTP (ej: 404 si el login es incorrecto)
        data = resp.json()
        if not data:
            break
        projects.extend(data)
        page += 1
    return projects

# --- DATA PROCESSING (Se mantiene igual) ---
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

# --- HTML GENERATORS (Se mantiene igual) ---
def generate_project_list(projects):
    if not projects:
        return "<p style='font-style:italic; color:#666;'>No projects yet</p>"

    html = "<div style='display:flex; flex-direction:column; gap:6px;'>\n"
    for p in sorted(projects, key=lambda x: x["name"].lower()):
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
    if not CLIENT_ID or not CLIENT_SECRET or not FT_42_LOGIN:
        print("❌ Error: CLIENT_ID, CLIENT_SECRET o FT_42_LOGIN no están configurados como variables de entorno.")
        exit(1)
        
    print(f"🔍 Fetching 42 projects for user: {FT_42_LOGIN}...")
    try:
        projects = get_projects()
        cursus_projects, piscine_projects = categorize_projects(projects)
        update_readme(cursus_projects, piscine_projects)
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP al llamar a la API: {e}")
        print("Asegúrate que tus credenciales de API son correctas y que el login existe.")
        exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        exit(1)
