# interfaz/ventana.py
# Abre una ventana de escritorio que muestra la presencia de Bridget.

import webview
import os

# Ruta al HTML de la presencia (relativa a este archivo, para portabilidad)
RUTA_HTML = os.path.join(os.path.dirname(__file__), "presencia.html")

def abrir_ventana():
    webview.create_window(
        title="Bridget",
        url=RUTA_HTML,
        width=500,
        height=500,
        background_color="#0a0e14",
        resizable=True
    )
    webview.start()

if __name__ == "__main__":
    abrir_ventana()