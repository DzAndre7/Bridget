import subprocess
import os
import sys
import base64
import requests
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

import builtins
_print_original = builtins.print

def _print_seguro(*args, **kwargs):
    try:
        _print_original(*args, **kwargs)
    except UnicodeEncodeError:
        pass

builtins.print = _print_seguro

@contextmanager
def silenciar_salida():
    with open(os.devnull, "w") as devnull:
        viejo_stdout = sys.stdout
        viejo_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = viejo_stdout
            sys.stderr = viejo_stderr

AUDIO_SALIDA = "/tmp/bridget_respuesta.wav"

# --- Configuración de Google TTS (voz principal) ---
GOOGLE_API_KEY = os.getenv("GOOGLE_TTS_API_KEY")
GOOGLE_URL = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_API_KEY}"
VOZ_GOOGLE = "es-US-Chirp3-HD-Enceladus"
IDIOMA_GOOGLE = "es-US"

# --- Coqui (voz de respaldo) se carga SOLO si hace falta ---
_tts_local = None  # arranca en None; se carga la primera vez que falle Google

def _cargar_coqui():
    """Carga Coqui solo cuando se necesita (respaldo). Así no ocupa GPU de gusto."""
    global _tts_local
    if _tts_local is None:
        from TTS.api import TTS
        with silenciar_salida():
            _tts_local = TTS(model_name="tts_models/es/css10/vits", progress_bar=False).to("cuda")
    return _tts_local

def _generar_google(texto):
    """Intenta generar el audio con Google. Devuelve True si lo logró."""
    if not GOOGLE_API_KEY:
        return False
    payload = {
        "input": {"text": texto},
        "voice": {"languageCode": IDIOMA_GOOGLE, "name": VOZ_GOOGLE},
        "audioConfig": {"audioEncoding": "LINEAR16"}
    }
    try:
        respuesta = requests.post(GOOGLE_URL, json=payload, timeout=15)
        if respuesta.status_code == 200:
            audio_bytes = base64.b64decode(respuesta.json()["audioContent"])
            with open(AUDIO_SALIDA, "wb") as f:
                f.write(audio_bytes)
            return True
        else:
            _print_original(f"Google TTS error {respuesta.status_code}, usando voz local.")
            return False
    except Exception as e:
        _print_original(f"Google TTS falló ({e}), usando voz local.")
        return False

def _generar_coqui(texto):
    """Respaldo: genera con Coqui local."""
    try:
        modelo = _cargar_coqui()
        with silenciar_salida():
            modelo.tts_to_file(text=texto, file_path=AUDIO_SALIDA)
        return True
    except Exception as e:
        _print_original(f"Error generando audio local: {e}")
        return False

def _generar(texto):
    """Genera el audio: prueba Google primero, cae a Coqui si falla."""
    if _generar_google(texto):
        return True
    return _generar_coqui(texto)

def hablar(texto):
    if _generar(texto):
        subprocess.run(["paplay", AUDIO_SALIDA])

def hablar_interrumpible(texto):
    if _generar(texto):
        proceso = subprocess.Popen(["paplay", AUDIO_SALIDA])
        return proceso
    return None

def generar_audio(texto):
    """Genera audio sin reproducir. Retorna la ruta del archivo."""
    if _generar(texto):
        return AUDIO_SALIDA
    return None