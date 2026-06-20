
import subprocess
import sys 

def _comando_abrir():
    if sys.platform.startswith("linux"):
        return "xdg-open"
    elif sys.platform == "darwin":
        return "open"
    elif sys.platform.startswith("win"):
        return "start"
    return "xdg-open"

def abrir_programa(nombre_programa):
    nombre_programa = nombre_programa.lower().strip()
    comando = _comando_abrir()
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen([nombre_programa], shell=True)
        else:
            subprocess.Popen([comando, nombre_programa])
        return True 
    except Exception:
        return False

def buscar_en_internet(consulta):
    if not consulta.strip():
        return False
    url = f"https://www.google.com/search?q={consulta.replace(' ', '+')}"
    comando = _comando_abrir()
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen([comando, url], shell=True)
        else:
            subprocess.Popen([comando, url])
        return True
    except Exception:
        return False

