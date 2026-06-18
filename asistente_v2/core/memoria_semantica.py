import json
import os
import ollama
from datetime import datetime

MEMORIA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memoria_semantica.json")
MODELO_EMBEDDINGS = "nomic-embed-text-v2-moe"

def obtener_embedding(texto, tipo="document"):
    prefijo = "search_query: " if tipo == "query" else "search_document: "
    respuesta = ollama.embeddings(model=MODELO_EMBEDDINGS, prompt=prefijo + texto)
    return respuesta["embedding"]

def similitud(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na = sum(x**2 for x in a)**0.5
    nb = sum(x**2 for x in b)**0.5
    return dot/(na*nb)

def cargar_memoria():
    if not os.path.exists(MEMORIA_FILE):
        return []
    try:
        with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def guardar_recuerdo(texto, categoria="general"):
    memoria = cargar_memoria()
    embedding = obtener_embedding(texto)
    recuerdo = {
        "texto": texto,
        "categoria": categoria,
        "embedding": embedding,
        "fecha": datetime.now().isoformat()
    }
    memoria.append(recuerdo)
    with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)
    return True

def recordar(consulta, top_k=3, umbral=0.3):
    memoria = cargar_memoria()
    if not memoria:
        return []
    embedding_consulta = obtener_embedding(consulta, tipo="query")
    scored = []
    for recuerdo in memoria:
        if "embedding" not in recuerdo:
            continue
        score = similitud(embedding_consulta, recuerdo["embedding"])
        if score >= umbral:
            scored.append((score, recuerdo))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]