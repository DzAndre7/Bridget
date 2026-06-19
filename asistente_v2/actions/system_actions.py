
import subprocess

def abrir_programa(nombre_programa):
    nombre_programa = nombre_programa.lower().strip()
    try:
        subprocess.Popen(["xdg-open", nombre_programa])
        return True
    except Exception:
        try:
            subprocess.Popen([nombre_programa])
            return True
        except Exception:
            return False

def buscar_en_internet(consulta):
    if not consulta.strip():
        return False
    url = f"https://www.google.com/search?q={consulta.replace(' ', '+')}"
    subprocess.Popen(["xdg-open", url])
    return True