import whisper
import sounddevice as sd
import numpy as np 
import webrtcvad
from scipy.io.wavfile import write

MODELO_WHISPER = whisper.load_model("base", device= "cpu")
ARCHIVO_TEMP = "/tmp/rick_escucha.wav"
FRECUENCIA = 16000
DURACION_SILENCIO = 1.6 # segundos de silencio para cortar

def escuchar():
    print("🎙️ Escuchando...")

    vad = webrtcvad.Vad(2) #agresividad 0-3

    frames = []
    silencio_frames = 0 
    hablando = False 
    frames_por_segundo = 50 
    frame_duracion = 1000 // frames_por_segundo #ms por frame
    frame_size = FRECUENCIA * frame_duracion // 1000 

    with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype='int16') as stream:
        while True:
            frame, _ = stream.read(frame_size)
            frame_bytes = frame.tobytes()

            es_voz = vad.is_speech(frame_bytes, FRECUENCIA)

            if es_voz:
                hablando = True
                silencio_frames = 0 
                frames.append(frame)
            elif hablando:
                silencio_frames += 1 
                frames.append(frame)

                if silencio_frames > frames_por_segundo * DURACION_SILENCIO:
                    break

    audio = np.concatenate(frames, axis=0)
    write(ARCHIVO_TEMP, FRECUENCIA, audio)

    print(" 🎬 Procesando...")
    resultado = MODELO_WHISPER.transcribe(ARCHIVO_TEMP, language="es")
    return resultado["text"].strip()

def escuchar_audio(ruta_archivo):
    try:
        resultado = MODELO_WHISPER.transcribe(ruta_archivo, language="es")
        return resultado["text"].strip()
    except Exception as e:
        print(f"Error al transcibir: {e}")
        return None

def escuchar_fragmento(duracion=1.5):
    import sounddevice as sd 
    import numpy as np 
    from scipy.io.wavfile import write

    audio = sd.rec(int(duracion * FRECUENCIA), samplerate=FRECUENCIA, channels=1, dtype='int16')
    sd.wait()
    write("/tmp/rick_fragmento.wav", FRECUENCIA, audio)
    resultado = MODELO_WHISPER.transcribe("/tmp/rick_fragmento.wav", language="es")
    return resultado["text"].strip().lower()