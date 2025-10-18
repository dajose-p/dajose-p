<!-- Header -->
<h1 align="center">👋 Hi there! I'm Daniel José Pereira</h1>
<h3 align="center">💻 Student at <a href="https://www.42madrid.com/" target="_blank">42 Madrid</a> | Passionate about Systems, C Programming & Automation</h3>

<!-- Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/C%20Language-00599C?style=for-the-badge&logo=c&logoColor=white" />
  <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" />
  <img src="https://img.shields.io/badge/Shell_Scripting-121011?style=for-the-badge&logo=gnu-bash&logoColor=white" />
  <img src="https://img.shields.io/badge/42%20Network-000000?style=for-the-badge&logo=42&logoColor=white" />
</p>

---

### 🚀 About Me

- 🎓 I’m currently a **student at [42 Madrid](https://www.42madrid.com/)**, part of the **42 global network**.  
- 🧠 Constantly learning about **low-level programming, system architecture, and network automation**.  
- ⚙️ I love building tools that make workflows faster and more efficient.  
- 🏗️ Working on projects that combine **C, Bash, and web APIs**.  

---

### 📂 My 42 Projects (via the 42 API)

Below you can see a dynamic view of my **completed** and **in-progress** projects fetched from the **42 API**.

> ⚡ This section updates automatically to reflect my real-time progress at 42 Madrid.

```python
# Example endpoint usage (Python)
import requests

API_URL = "https://api.intra.42.fr/v2/users/dpereira/projects_users"
headers = {"Authorization": f"Bearer <YOUR_ACCESS_TOKEN>"}

projects = requests.get(API_URL, headers=headers).json()
for project in projects:
    print(f"{project['project']['name']} - {project['status']} ({project['final_mark']})")
