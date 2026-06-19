
# Bridget — Asistente personal con IA local

Bridget es un asistente personal de código abierto que corre casi
completamente en tu máquina, sin depender de servicios externos de pago.
Construido desde cero por un programador autodidacta.

## ¿Qué puede hacer hoy?

- Conversación por voz bidireccional (STT + TTS en español)
- Control del sistema: abrir aplicaciones
- Memoria semántica: recuerda cosas por significado, no por palabra exacta
- Revisor de código con modelo experto externo (Groq)
- Auto-auditoría: revisa y mejora su propio código
- Interfaz web con modo manos libres
- API remota con autenticación

## Dependencias externas opcionales

Bridget es principalmente local, pero tiene dos capacidades que
requieren conexión a internet:

- Búsqueda web: busca en internet si se lo pedís
- Revisor de código: usa Groq (gratuito) para auditar y mejorar código

Todo lo demás — conversación, voz, memoria, control del sistema —
corre completamente offline.

## Stack

- LLM: dolphin3:8b via Ollama (local, sin censura)
- Embeddings: nomic-embed-text-v2-moe (multilingüe)
- STT: Whisper + webrtcvad
- TTS: Coqui TTS
- API: FastAPI + ngrok

## Instalación paso a paso

### Paso 1 — Instalar lo básico
Necesitás tener instalado en tu sistema:
- Python 3.11
- Ollama (https://ollama.com) — el programa que corre los modelos de IA
- Git — para descargar el proyecto

### Paso 2 — Descargar los modelos de IA
Ollama necesita descargar dos modelos. Abrí una terminal y corré:
\`\`\`bash
ollama pull dolphin3:8b
ollama pull nomic-embed-text-v2-moe
\`\`\`
Esto puede tardar un rato la primera vez (son varios GB).

### Paso 3 — Descargar el proyecto
\`\`\`bash
git clone https://github.com/bridget/bridget.git
cd bridget
\`\`\`

### Paso 4 — Crear el entorno de Python
Esto crea un espacio aislado para las dependencias del proyecto:
\`\`\`bash
python -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
\`\`\`

### Paso 5 — Configurar las claves
Creá un archivo llamado \`.env\` en la carpeta del proyecto con este contenido:
\`\`\`
GROQ_API_KEY=tu_clave_de_groq
RICK_API_KEY=una_clave_que_inventes_para_la_web
\`\`\`
La de Groq se saca gratis en groq.com. La otra la inventás vos.

### Paso 6 — Arrancar
\`\`\`bash
source venv311/bin/activate
python main.py
\`\`\`
¡Listo! Ya podés hablar con tu asistente.


### Cambiar el nombre del asistente
Editá \`config.py\` y cambiá \`ASSISTANT_NAME\` por el nombre que quieras.

## Estado del proyecto

Bridget está en desarrollo activo. Funciona y tiene base sólida,
pero hay bugs y limitaciones reales — especialmente en la fluidez
de la conversación, limitada por el modelo de 8B parámetros.
El objetivo a futuro es un asistente que no solo ejecute tareas
sino que acompañe el pensamiento.
EOF