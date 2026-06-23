# interfaz/ventana.py
import webview
import os
import sys
import json

DIR = os.path.dirname(__file__)
RUTA_HTML = os.path.join(DIR, "presencia.html")
RUTA_CONFIG = os.path.join(DIR, "config_presencia.json")

# Agregamos la raíz del proyecto al path para poder importar 'core'
RAIZ = os.path.dirname(DIR)  # sube de interfaz/ a asistente_v2/
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from core.brain import procesar_comando
from config import ASSISTANT_NAME


class API:
    """Puente entre el JavaScript de la ventana y Python."""

    def guardar_config(self, config_json):
        try:
            with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
                f.write(config_json)
            return True
        except Exception as e:
            print(f"Error guardando config: {e}")
            return False

    def cargar_config(self):
        if not os.path.exists(RUTA_CONFIG):
            return ""
        try:
            with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error leyendo config: {e}")
            return ""

    def enviar_mensaje(self, texto):
        """El chat llama a esto. Pasa el mensaje al cerebro de Bridget y devuelve la respuesta."""
        try:
            respuesta = procesar_comando(texto, ASSISTANT_NAME)
            return respuesta
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            return "Tuve un problema procesando eso."


def abrir_ventana():
    api = API()
    webview.create_window(
        title="Bridget",
        url=RUTA_HTML,
        width=500,
        height=500,
        background_color="#0a0e14",
        resizable=True,
        transparent=True,
        js_api=api
    )
    webview.start()


if __name__ == "__main__":
    abrir_ventana()