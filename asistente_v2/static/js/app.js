const API_URL = "https://cling-immodest-case.ngrok-free.dev/chat";
const API_AUDIO_URL = "https://cling-immodest-case.ngrok-free.dev/audio";
const API_UPLOAD_URL = "https://cling-immodest-case.ngrok-free.dev/upload";
const API_INBOX_URL = "https://cling-immodest-case.ngrok-free.dev/inbox";
const API_DELETE_URL = "https://cling-immodest-case.ngrok-free.dev/inbox";
const API_CHAT_ARCHIVO_URL = "https://cling-immodest-case.ngrok-free.dev/chat-archivo";
const API_SPEAK_URL = "https://cling-immodest-case.ngrok-free.dev/speak";
const API_KEY = "kyy007351andy's#key";

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const send = document.getElementById("send");
const mic = document.getElementById("mic");
const handsfree = document.getElementById("handsfree");
const attach = document.getElementById("attach");
const inboxModal = document.getElementById("inbox-modal");
const modalClose = document.getElementById("modal-close");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const filesList = document.getElementById("files-list");
const selectedInfo = document.getElementById("selected-info");

let grabando = false;
let mediaRecorder;
let audioChunks = [];
let audioContext;
let stream;
let archivoSeleccionado = null;

function agregarMensaje(texto, tipo) {
    const div = document.createElement("div");
    div.className = `mensaje ${tipo}`;
    if (tipo === "rick") {
        const nombreDiv = document.createElement("div");
        nombreDiv.className = "nombre";
        nombreDiv.textContent = "RICK //";
        div.appendChild(nombreDiv);

        const textoDiv = document.createElement("div");
        textoDiv.textContent = texto;
        div.appendChild(textoDiv);

        // Agregar contenedor para controles de voz
        const audioDiv = document.createElement("div");
        audioDiv.className = "rick-audio";
        div.appendChild(audioDiv);

        // Crear botón para iniciar reproducción
        const btnVoz = document.createElement("button");
        btnVoz.textContent = "🔊 ESCUCHAR";
        btnVoz.addEventListener("click", () => reproducirRespuesta(texto, audioDiv));
        audioDiv.appendChild(btnVoz);
    } else {
        div.textContent = texto;
    }
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

async function reproducirRespuesta(texto, audioContainer) {
    try {
        // Reutilizar el botón ya existente (creado en agregarMensaje)
        const btn = audioContainer.querySelector("button");
        const audioState = audioContainer.dataset.audioState || "none";

        if (audioState === "none") {
            btn.textContent = "⏳ GENERANDO...";
            btn.disabled = true;
            audioContainer.dataset.audioState = "generating";

            const res = await fetch(API_SPEAK_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-api-key": API_KEY
                },
                body: JSON.stringify({ texto })
            });

            if (!res.ok) {
                throw new Error("Error generando audio");
            }

            const audioBlob = await res.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audioContainer.dataset.audio = audioUrl;
            audioContainer.audio = audio;

            btn.disabled = false;
            btn.textContent = "🔊 ESCUCHAR";
            audioContainer.dataset.audioState = "ready";

            let pauseTimeout = null;

            btn.onclick = (e) => {
                e.stopPropagation();
                const currentState = audioContainer.dataset.audioState;

                if (currentState === "playing") {
                    // Pause
                    audio.pause();
                    btn.textContent = "⏸️ PAUSADO";
                    audioContainer.dataset.audioState = "paused";

                    // Auto-stop después de 15s
                    pauseTimeout = setTimeout(() => {
                        audio.pause();
                        audio.currentTime = 0;
                        btn.textContent = "🔊 ESCUCHAR";
                        btn.classList.remove("activo");
                        audioContainer.dataset.audioState = "ready";
                    }, 15000);

                } else if (currentState === "paused") {
                    // Resume
                    if (pauseTimeout) {
                        clearTimeout(pauseTimeout);
                        pauseTimeout = null;
                    }
                    audio.play();
                    btn.textContent = "⏸️ REPRODUCIENDO";
                    btn.classList.add("activo");
                    audioContainer.dataset.audioState = "playing";

                } else if (currentState === "ready") {
                    // Play
                    audio.play();
                    btn.textContent = "⏸️ REPRODUCIENDO";
                    btn.classList.add("activo");
                    audioContainer.dataset.audioState = "playing";
                }
            };

            audio.onended = () => {
                btn.textContent = "🔊 ESCUCHAR";
                btn.classList.remove("activo");
                audioContainer.dataset.audioState = "ready";
                if (pauseTimeout) clearTimeout(pauseTimeout);
            };

            audio.onerror = () => {
                btn.textContent = "🔊 ERROR";
                btn.disabled = true;
            };
        }

    } catch (e) {
        console.error("Error:", e);
        const btn = audioContainer.querySelector("button");
        if (btn) {
            btn.textContent = "🔊 ESCUCHAR";
            btn.disabled = false;
        }
        audioContainer.dataset.audioState = "none";
    }
}

// ============ MODAL ============
attach.addEventListener("click", () => {
    inboxModal.classList.add("abierto");
    cargarArchivos();
});

modalClose.addEventListener("click", () => {
    inboxModal.classList.remove("abierto");
});

inboxModal.addEventListener("click", (e) => {
    if (e.target === inboxModal) {
        inboxModal.classList.remove("abierto");
    }
});

// ============ AUDIO ============
async function iniciarGrabacion() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
            await enviarAudio(audioBlob);
        };

        mediaRecorder.start();
        grabando = true;
        mic.classList.add("grabando");
        mic.textContent = "⏹️";
    } catch (e) {
        agregarMensaje("Error al acceder al micrófono.", "rick");
    }
}

function detenerGrabacion() {
    if (mediaRecorder && grabando) {
        mediaRecorder.stop();
        grabando = false;
        mic.classList.remove("grabando");
        mic.textContent = "🎙️";
        stream.getTracks().forEach(track => track.stop());
    }
}

async function enviarAudio(audioBlob) {
    const cargando = document.createElement("div");
    cargando.className = "mensaje rick cargando";
    cargando.textContent = "transcribiendo...";
    chat.appendChild(cargando);

    try {
        const formData = new FormData();
        formData.append("file", audioBlob, "audio.wav");

        const res = await fetch(API_AUDIO_URL, {
            method: "POST",
            headers: {
                "x-api-key": API_KEY
            },
            body: formData
        });
        const data = await res.json();
        chat.removeChild(cargando);

        if (data.error) {
            agregarMensaje(`Error: ${data.error}`, "rick");
        } else {
            input.value = data.texto_transcrito;
            input.focus();
        }
    } catch (e) {
        if (chat.contains(cargando)) {
            chat.removeChild(cargando);
        }
        agregarMensaje("Error de conexión.", "rick");
    }
}

// ============ MANOS LIBRES ============
let manosLibresActivo = false;
let manosLibresStreamActual = null;
let manosLibresAudioActual = null;

const UMBRAL_VOZ = 12;          // umbral de volumen (0-255) para considerar que hay voz
const SILENCIO_MS = 1600;       // silencio para cortar la grabación
const ESPERA_MAX_MS = 8000;     // tiempo máximo esperando que el usuario empiece a hablar
const GRABACION_MAX_MS = 15000; // tope de seguridad por grabación
const FRASES_SALIDA = ["salir del modo voz", "salir modo voz", "salir manos libres", "salir de manos libres", "modo texto"];

handsfree.addEventListener("click", () => {
    if (manosLibresActivo) {
        detenerManosLibres();
    } else {
        iniciarManosLibres();
    }
});

function agregarEstado(texto) {
    const div = document.createElement("div");
    div.className = "mensaje rick cargando";
    div.textContent = texto;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function iniciarManosLibres() {
    manosLibresActivo = true;
    handsfree.classList.add("activo");
    agregarEstado("🤚 Modo manos libres activado. Te escucho...");
    cicloManosLibres();
}

function detenerManosLibres() {
    manosLibresActivo = false;
    handsfree.classList.remove("activo", "grabando");

    if (manosLibresAudioActual) {
        manosLibresAudioActual.pause();
        manosLibresAudioActual = null;
    }
    if (manosLibresStreamActual) {
        manosLibresStreamActual.getTracks().forEach(track => track.stop());
        manosLibresStreamActual = null;
    }
    agregarEstado("🤚 Modo manos libres desactivado.");
}

async function cicloManosLibres() {
    while (manosLibresActivo) {
        handsfree.classList.add("grabando");
        const estadoEscucha = agregarEstado("🎙️ escuchando...");
        const audioBlob = await escucharConVAD();
        if (chat.contains(estadoEscucha)) chat.removeChild(estadoEscucha);
        handsfree.classList.remove("grabando");

        if (!manosLibresActivo) break;
        if (!audioBlob) continue; // no se detectó voz, reintentar

        const estadoTranscribe = agregarEstado("🎬 transcribiendo...");
        let texto_transcrito;
        try {
            const formData = new FormData();
            formData.append("file", audioBlob, "audio.wav");
            const res = await fetch(API_AUDIO_URL, {
                method: "POST",
                headers: { "x-api-key": API_KEY },
                body: formData
            });
            const data = await res.json();
            if (chat.contains(estadoTranscribe)) chat.removeChild(estadoTranscribe);

            if (data.error || !data.texto_transcrito) continue;
            texto_transcrito = data.texto_transcrito.trim();
        } catch (e) {
            if (chat.contains(estadoTranscribe)) chat.removeChild(estadoTranscribe);
            continue;
        }

        if (!texto_transcrito) continue;

        const textoLower = texto_transcrito.toLowerCase();
        if (FRASES_SALIDA.some(frase => textoLower.includes(frase))) {
            detenerManosLibres();
            break;
        }

        agregarMensaje(texto_transcrito, "usuario");

        const cargando = document.createElement("div");
        cargando.className = "mensaje rick cargando";
        cargando.textContent = "procesando...";
        chat.appendChild(cargando);

        let respuesta;
        try {
            const res = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
                body: JSON.stringify({ texto: texto_transcrito })
            });
            const data = await res.json();
            if (chat.contains(cargando)) chat.removeChild(cargando);
            if (data.error) {
                agregarMensaje(`Error: ${data.error}`, "rick");
                continue;
            }
            respuesta = data.respuesta;
            agregarMensaje(respuesta, "rick");
        } catch (e) {
            if (chat.contains(cargando)) chat.removeChild(cargando);
            agregarMensaje("Error de conexión.", "rick");
            continue;
        }

        if (!manosLibresActivo) break;
        await reproducirYesperar(respuesta);
    }
}

function reproducirYesperar(texto) {
    return new Promise(async (resolve) => {
        try {
            const res = await fetch(API_SPEAK_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
                body: JSON.stringify({ texto })
            });
            if (!res.ok) return resolve();

            const audioBlob = await res.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            manosLibresAudioActual = audio;

            audio.onended = () => { manosLibresAudioActual = null; resolve(); };
            audio.onerror = () => { manosLibresAudioActual = null; resolve(); };
            audio.play();
        } catch (e) {
            resolve();
        }
    });
}

function escucharConVAD() {
    return new Promise(async (resolve) => {
        let stream, audioContext, analyser, recorder, intervalo;
        let chunks = [];
        let hablando = false;
        let ultimaVoz = Date.now();
        const inicio = Date.now();
        let finalizado = false;

        const limpiar = () => {
            if (intervalo) clearInterval(intervalo);
            if (stream) stream.getTracks().forEach(t => t.stop());
            if (audioContext && audioContext.state !== "closed") audioContext.close();
            if (manosLibresStreamActual === stream) manosLibresStreamActual = null;
        };

        const terminar = (resultado) => {
            if (finalizado) return;
            finalizado = true;
            limpiar();
            resolve(resultado);
        };

        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            terminar(null);
            return;
        }

        if (!manosLibresActivo) {
            stream.getTracks().forEach(t => t.stop());
            terminar(null);
            return;
        }

        manosLibresStreamActual = stream;
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const fuente = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        fuente.connect(analyser);
        const datos = new Uint8Array(analyser.frequencyBinCount);

        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = () => {
            terminar(hablando ? new Blob(chunks, { type: "audio/wav" }) : null);
        };
        recorder.start();

        intervalo = setInterval(() => {
            if (!manosLibresActivo) {
                if (recorder.state !== "inactive") recorder.stop();
                else terminar(null);
                return;
            }

            analyser.getByteTimeDomainData(datos);
            let suma = 0;
            for (let i = 0; i < datos.length; i++) {
                const valor = datos[i] - 128;
                suma += valor * valor;
            }
            const volumen = Math.sqrt(suma / datos.length);
            const ahora = Date.now();

            if (volumen > UMBRAL_VOZ) {
                hablando = true;
                ultimaVoz = ahora;
            } else if (hablando && ahora - ultimaVoz > SILENCIO_MS) {
                recorder.stop();
                return;
            }

            if (!hablando && ahora - inicio > ESPERA_MAX_MS) {
                recorder.stop();
                return;
            }

            if (ahora - inicio > GRABACION_MAX_MS) {
                recorder.stop();
                return;
            }
        }, 50);
    });
}

// ============ CHAT ============
async function enviar() {
    const texto = input.value.trim();
    if (!texto) return;

    agregarMensaje(texto, "usuario");
    input.value = "";

    const cargando = document.createElement("div");
    cargando.className = "mensaje rick cargando";
    cargando.textContent = "procesando...";
    chat.appendChild(cargando);

    try {
        let url = API_URL;
        let body = { texto };

        // Si hay archivo seleccionado, usar endpoint de chat-archivo
        if (archivoSeleccionado) {
            url = API_CHAT_ARCHIVO_URL + "?nombre=" + encodeURIComponent(archivoSeleccionado);
        }

        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-api-key": API_KEY
            },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        chat.removeChild(cargando);
        if (data.error) {
            agregarMensaje(`Error: ${data.error}`, "rick");
        } else {
            agregarMensaje(data.respuesta, "rick");
        }
    } catch (e) {
        chat.removeChild(cargando);
        agregarMensaje("Error de conexión.", "rick");
    }
}

// ============ INBOX ============
async function cargarArchivos() {
    try {
        const res = await fetch(API_INBOX_URL, {
            headers: {
                "x-api-key": API_KEY
            }
        });
        const data = await res.json();
        mostrarArchivos(data.archivos);
    } catch (e) {
        console.error("Error cargando archivos:", e);
    }
}

function mostrarArchivos(archivos) {
    filesList.innerHTML = "";

    if (archivos.length === 0) {
        filesList.innerHTML = '<div style="color: #00ff8866; font-size: 11px; text-align: center; padding: 20px;">Sin archivos subidos</div>';
        return;
    }

    archivos.forEach(archivo => {
        const div = document.createElement("div");
        div.className = "file-item";
        if (archivoSeleccionado === archivo.nombre) {
            div.classList.add("seleccionado");
        }

        div.innerHTML = `
            <span class="file-name">${archivo.nombre}</span>
            <button class="file-delete">✕</button>
        `;

        div.querySelector(".file-delete").addEventListener("click", (e) => {
            e.stopPropagation();
            eliminarArchivo(archivo.nombre);
        });

        div.addEventListener("click", () => {
            document.querySelectorAll(".file-item").forEach(f => f.classList.remove("seleccionado"));
            div.classList.add("seleccionado");
            archivoSeleccionado = archivo.nombre;
            attach.classList.add("activo");
            selectedInfo.textContent = `✓ ${archivo.nombre} seleccionado`;
            selectedInfo.classList.add("activo");
        });

        filesList.appendChild(div);
    });
}

async function subirArchivo(file) {
    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(API_UPLOAD_URL, {
            method: "POST",
            headers: {
                "x-api-key": API_KEY
            },
            body: formData
        });

        if (res.ok) {
            cargarArchivos();
        } else {
            const data = await res.json();
            agregarMensaje(`Error: ${data.detail}`, "rick");
        }
    } catch (e) {
        agregarMensaje("Error al subir archivo.", "rick");
    }
}

async function eliminarArchivo(nombre) {
    try {
        const res = await fetch(API_DELETE_URL + "/" + encodeURIComponent(nombre), {
            method: "DELETE",
            headers: {
                "x-api-key": API_KEY
            }
        });

        if (res.ok) {
            if (archivoSeleccionado === nombre) {
                archivoSeleccionado = null;
                attach.classList.remove("activo");
                selectedInfo.textContent = "Sin archivo seleccionado";
                selectedInfo.classList.remove("activo");
            }
            cargarArchivos();
        }
    } catch (e) {
        console.error("Error eliminando archivo:", e);
    }
}

// ============ EVENT LISTENERS ============
send.addEventListener("click", enviar);
input.addEventListener("keypress", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        enviar();
    }
});

// Auto-ajustar altura del textarea
input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 100) + "px";
});

mic.addEventListener("mousedown", iniciarGrabacion);
mic.addEventListener("mouseup", detenerGrabacion);
mic.addEventListener("mouseleave", detenerGrabacion);

mic.addEventListener("touchstart", (e) => {
    e.preventDefault();
    iniciarGrabacion();
});
mic.addEventListener("touchend", (e) => {
    e.preventDefault();
    detenerGrabacion();
});

// Mantener el último mensaje visible cuando aparece el teclado virtual
input.addEventListener("focus", () => {
    setTimeout(() => { chat.scrollTop = chat.scrollHeight; }, 300);
});
if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
        chat.scrollTop = chat.scrollHeight;
    });
}

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");

    const files = e.dataTransfer.files;
    for (let file of files) {
        subirArchivo(file);
    }
});

fileInput.addEventListener("change", (e) => {
    const files = e.target.files;
    for (let file of files) {
        subirArchivo(file);
    }
    fileInput.value = "";
});
