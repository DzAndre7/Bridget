
from config import ASSISTANT_NAME
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from core.brain import procesar_comando
from core.code_analyzer import listar_reportes, obtener_reporte
from core.listen import escuchar_audio
from core.voice import generar_audio
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import os
import io

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

API_KEY = os.environ.get("BRIDGET_API_KEY", "")

class Mensaje(BaseModel):
    texto: str

@app.post("/chat")
async def chat(mensaje: Mensaje, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")
    respuesta = procesar_comando(mensaje.texto, ASSISTANT_NAME)
    return {"respuesta": respuesta}

@app.post("/audio")
async def audio(file: UploadFile = File(...), x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        contenido = await file.read()

        ruta_temp = "/tmp/bridget_audio_api.wav"
        with open(ruta_temp, "wb") as f:
            f.write(contenido)

        texto_transcrito = escuchar_audio(ruta_temp)

        if not texto_transcrito:
            return {"error": "No se pudo transcribir el audio"}

        respuesta = procesar_comando(texto_transcrito, ASSISTANT_NAME)
        return {
            "texto_transcrito": texto_transcrito,
            "respuesta": respuesta
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/reportes")
async def listar_reportes_endpoint(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")
    reportes = listar_reportes()
    return {"reportes": reportes}

@app.get("/reportes/{nombre}")
async def obtener_reporte_endpoint(nombre: str, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")
    contenido = obtener_reporte(nombre)
    if not contenido:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return {"nombre": nombre, "contenido": contenido}

# INBOX ENDPOINTS

INBOX_DIR = os.path.join(os.path.dirname(__file__), "inbox")
EXTENSIONES_PERMITIDAS = {".py", ".txt", ".md", ".json"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no permitido. Soportados: {', '.join(EXTENSIONES_PERMITIDAS)}")

    try:
        contenido = await file.read()
        ruta_archivo = os.path.join(INBOX_DIR, file.filename)

        with open(ruta_archivo, "wb") as f:
            f.write(contenido)

        return {
            "nombre": file.filename,
            "ruta": ruta_archivo,
            "tamaño": len(contenido)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inbox")
async def listar_inbox(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    if not os.path.exists(INBOX_DIR):
        return {"archivos": []}

    archivos = []
    for nombre in os.listdir(INBOX_DIR):
        if nombre.startswith("."):
            continue

        ruta = os.path.join(INBOX_DIR, nombre)
        if os.path.isfile(ruta):
            archivos.append({
                "nombre": nombre,
                "tamaño": os.path.getsize(ruta),
                "modificado": os.path.getmtime(ruta)
            })

    return {"archivos": archivos}

@app.delete("/inbox/{nombre}")
async def delete_archivo(nombre: str, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    ruta = os.path.join(INBOX_DIR, nombre)

    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        os.remove(ruta)
        return {"mensaje": f"Archivo '{nombre}' eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat-archivo")
async def chat_archivo(nombre: str, mensaje: Mensaje, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    ruta = os.path.join(INBOX_DIR, nombre)

    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            contenido_archivo = f.read()

        # Crear contexto con el archivo
        prompt_contexto = f"""El usuario está haciendo una pregunta sobre este archivo: {nombre}

CONTENIDO DEL ARCHIVO:
```
{contenido_archivo}
```

PREGUNTA DEL USUARIO:
{mensaje.texto}

Por favor, responde basándote en el contenido del archivo."""

        respuesta = procesar_comando(prompt_contexto, ASSISTANT_NAME)
        return {"respuesta": respuesta}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/speak")
async def speak(mensaje: Mensaje, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        ruta_audio = generar_audio(mensaje.texto)

        if not ruta_audio or not os.path.exists(ruta_audio):
            raise HTTPException(status_code=500, detail="Error generando audio")

        return FileResponse(
            path=ruta_audio,
            media_type="audio/wav",
            filename="respuesta.wav"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


