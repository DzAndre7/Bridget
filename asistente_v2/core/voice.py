import subprocess
from TTS.api import TTS

MODELO = "tts_models/es/css10/vits"
AUDIO_SALIDA = "/tmp/rick_respuesta.wav"

tts = TTS(model_name=MODELO, progress_bar=False).to("cuda")

def hablar(texto):
    tts.tts_to_file(
        text=texto,
        file_path=AUDIO_SALIDA
    )
    subprocess.run(["paplay", AUDIO_SALIDA])

def hablar_interrumpible(texto):
    tts.tts_to_file(text=texto, file_path=AUDIO_SALIDA)
    proceso = subprocess.Popen(["paplay", AUDIO_SALIDA])
    return proceso

def generar_audio(texto):
    """Genera audio sin reproducir. Retorna la ruta del archivo."""
    try:
        tts.tts_to_file(
            text=texto,
            file_path=AUDIO_SALIDA
        )
        return AUDIO_SALIDA
    except Exception as e:
        print(f"Error generando audio: {e}")
        return None
