# interfaz/ventana.py
import webview
import os
import json

DIR = os.path.dirname(__file__)
RUTA_HTML = os.path.join(DIR, "presencia.html")
RUTA_CONFIG = os.path.join(DIR, "config_presencia.json")


class API:
    """Puente entre el JavaScript de la presencia y el disco."""

    def guardar_config(self, config_json):
        """El JS llama a esto para guardar la configuración en disco."""
        try:
            with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
                f.write(config_json)
            return True
        except Exception as e:
            print(f"Error guardando config: {e}")
            return False

    def cargar_config(self):
        """El JS llama a esto al arrancar para recuperar la configuración."""
        if not os.path.exists(RUTA_CONFIG):
            return ""  # no hay config guardada todavía
        try:
            with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error leyendo config: {e}")
            return ""


def abrir_ventana():
    api = API()
    ventana = webview.create_window(
        title="Bridget",
        url=RUTA_HTML,
        width=500,
        height=500,
        background_color="#0a0e14",
        resizable=True,
        transparent=True,
        frameless=False,
        js_api=api          # expone la API al JavaScript
    )
    webview.start()


if __name__ == "__main__":
    abrir_ventana()