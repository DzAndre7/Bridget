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

    def generar_voz(self, texto):
        """Genera el audio de una respuesta con Enceladus y lo devuelve en base64."""
        import base64
        from core import voice
        try:
            # Reusamos la generación de voice.py: genera el archivo
            ruta = voice.generar_audio(texto)
            if not ruta:
                return ""
            with open(ruta, "rb") as f:
                audio_bytes = f.read()
            # lo codificamos en base64 para pasarlo por el puente
            return base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"Error generando voz: {e}")
            return ""

    def iniciar_microfono(self):
        """Empieza a grabar del micrófono."""
        from core import microfono_ventana
        try:
            microfono_ventana.iniciar_grabacion()
            return True
        except Exception as e:
            print(f"Error iniciando micrófono: {e}")
            return False

    def detener_microfono(self):
        """Para de grabar, transcribe, y devuelve el texto."""
        from core import microfono_ventana
        try:
            return microfono_ventana.detener_grabacion()
        except Exception as e:
            print(f"Error deteniendo micrófono: {e}")
            return ""


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