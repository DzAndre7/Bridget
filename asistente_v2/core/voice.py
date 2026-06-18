import subprocess
import os
import sys
from TTS.api import TTS
from contextlib import contextmanager

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

MODELO = "tts_models/es/css10/vits"
AUDIO_SALIDA = "/tmp/rick_respuesta.wav"

with silenciar_salida():
    tts = TTS(model_name=MODELO, progress_bar=False).to("cuda")

def hablar(texto):
    with silenciar_salida():
        tts.tts_to_file(
            text=texto,
            file_path=AUDIO_SALIDA
        )
    subprocess.run(["paplay", AUDIO_SALIDA])

def hablar_interrumpible(texto):
    with silenciar_salida():
        tts.tts_to_file(text=texto, file_path=AUDIO_SALIDA)
    proceso = subprocess.Popen(["paplay", AUDIO_SALIDA])
    return proceso

def generar_audio(texto):
    """Genera audio sin reproducir. Retorna la ruta del archivo."""
    try:
        with silenciar_salida():
            tts.tts_to_file(
                text=texto,
                file_path=AUDIO_SALIDA
        )
        return AUDIO_SALIDA
    except Exception as e:
        print(f"Error generando audio: {e}")
        return None
