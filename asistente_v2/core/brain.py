import datetime
import re
import unicodedata
import ollama
import subprocess
import shutil
import os

from core import cerebro
from config import ASSISTANT_NAME
from core.memoria_semantica import recordar, guardar_recuerdo as guardar_recuerdo_semantico
from actions.system_actions import buscar_en_internet, abrir_programa
from core.memory import cargar_recuerdos, guardar_recuerdo, leer_recuerdos, olvidar_recuerdo, borrar_todos_los_recuerdos
from core.preferences import cargar_preferencias, guardar_preferencia, obtener_preferencia
from core.vision import ver_pantalla
from actions.agent_actions import planificar_tarea, extraer_programa_con_llama, ALIAS_PROGRAMAS, buscar_aplicaciones_sistema
from core.search import buscar_web, formatear_resultados
from core.code_analyzer import analizar_archivo, analizar_proyecto, guardar_reporte
from core.dataset_collector import guardar_interaccion, guardar_par_entrenamiento
from core.code_reviewer import revisar_codigo
from core.auditoria import auditar_proyecto

DEBUG_MODE = False


class Sesion:
    """Estado mutable de UNA conversación: historial + flujo de confirmaciones.
    Aislarlo en un objeto permite que la API atienda a varios clientes sin que
    compartan historial ni confirmaciones. Antes eran globales de módulo y, con
    la API expuesta por ngrok, dos usuarios concurrentes se pisaban el estado
    (uno podía confirmar la tarea pendiente de otro, o ver su conversación)."""

    def __init__(self):
        self.historial = []
        self.opciones_pendientes = []
        self.esperando_confirmacion_borrado = False
        self.esperando_confirmacion_tarea = False
        self.plan_pendiente = ""
        self.plan_nombre = ""


# Sesión por defecto: la usa la CLI (un solo usuario) y cualquier llamada que no
# pase una sesión explícita. La API crea una Sesion por cliente (X-Session-Id).
_sesion_default = Sesion()

# Tope de mensajes que mandamos al modelo. Sin esto el historial crece sin
# límite: cada turno se hace más lento y más caro, y termina desbordando la
# ventana de contexto. 20 = ~10 intercambios recientes.
MAX_HISTORIAL = 20

# El contexto del proyecto (context.md) es estático: lo leemos una sola vez y
# lo cacheamos, en vez de tocar disco en cada turno de conversación.
_CONTEXTO_PROYECTO = None

def _cargar_contexto_proyecto():
    global _CONTEXTO_PROYECTO
    if _CONTEXTO_PROYECTO is None:
        ruta = os.path.join(os.path.dirname(__file__), "..", "context.md")
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                _CONTEXTO_PROYECTO = f.read()
        except Exception:
            _CONTEXTO_PROYECTO = ""
    return _CONTEXTO_PROYECTO

def normalizar_texto(texto):
    texto = texto.lower()

    #quita tildes
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def limpiar_texto_base(texto, assistant_name):
    texto = texto.lower().strip()

    ruido_inicial = [
        f"{assistant_name.lower()},",
        assistant_name.lower(),
        "hola",
        "buenas",
        "buenas noches",
        "buenas tardes",
        "buen día",
        "buen dia",
        "por favor",
        "podrías",
        "podrias",
        "podés",
        "podes",
        "che",
    ]

    ruido_inicial.sort(key=len, reverse=True)

    cambios = True
    while cambios:
        cambios = False
        
        for ruido in ruido_inicial: 
            if texto.startswith(ruido):
                texto = texto[len(ruido):].strip(" ,¿?.,;:!")
                cambios = True
    texto = " ".join(texto.split())
    return texto

def es_intencion_busqueda(texto):
    texto = texto.lower()

    verbos_busqueda = [
        "buscar", "busca", "buscá", "buscame", "búscame",
        "encontrar", "encontra", "encontrá",
        "averiguar", "averigua", "averiguá"
    ]

    contexto_web = [
        "internet", "google", "web", "online"
    ]

    tiene_verbo = any(verbo in texto for verbo in verbos_busqueda)
    tiene_contexto_web = any(palabra in texto for palabra in contexto_web)

    return tiene_verbo and tiene_contexto_web

def extraer_consulta_busqueda(texto, assistant_name):
    texto = limpiar_texto_base(texto, assistant_name)

    palabras_a_sacar = {
        "buscar", "busca", "buscá", "buscame", "búscame",
        "encontrar", "encontra", "encontrá",
        "averiguar", "averigua", "averiguá",
        "internet", "google", "web", "online",
    }

    # nos quedamos solo con las palabras que no son "comando de búsqueda".
    # (Antes, si la consulta eran TODAS palabras de comando, `consulta` quedaba
    # sin asignar y esto lanzaba UnboundLocalError, rompiendo procesar_comando.)
    consulta_limpia = [
        p.strip(" ,¿?.,;:!") for p in texto.split()
        if p.strip(" ,¿?.,;:!").lower() not in palabras_a_sacar
    ]

    consulta = " ".join(" ".join(consulta_limpia).split()).strip()

    # sacamos conectores sueltos que hayan quedado al inicio o al final
    for sufijo in (" en la", " en el", " en"):
        if consulta.endswith(sufijo):
            consulta = consulta[: -len(sufijo)].strip()
    for prefijo in ("en la ", "en el ", "en "):
        if consulta.startswith(prefijo):
            consulta = consulta[len(prefijo):].strip()

    return consulta if consulta else None

def _contiene(texto, frases):
    """True si alguna de `frases` aparece en `texto`, ignorando tildes.
    detectar_intencion recibe el texto ya normalizado (sin tildes), así que
    normalizamos cada frase para que las variantes con tilde también matcheen.
    Antes, entradas como 'buscá' o 'guardá' en las listas nunca matcheaban y
    solo funcionaban por estar duplicadas sin tilde: frágil de mantener."""
    return any(normalizar_texto(f) in texto for f in frases)


def detectar_intencion(texto):
    texto = texto.lower().strip()

    if _contiene(texto, [
        "busca en internet", "buscá en internet", "busca online", "modo conectado", "busca en la web"
    ]):
        return "buscar_web"

    elif es_intencion_busqueda(texto):
        return "buscar_en_internet"

    elif texto in ["s", "y", "confirmar borrado"]:
        return "confirmar_borrado"

    elif _contiene(texto, [
        "guarda esto", "guardá esto", "guarda eso", "guardá eso",
        "anota esto", "anotá esto", "anota eso", "anotá eso",
        "guarda en tu cerebro", "guardá en tu cerebro",
        "guarda en el cerebro", "guardá en el cerebro",
        "guarda esto en tu cerebro", "guardá esto en tu cerebro"
    ]):
        return "guardar_en_cerebro"

    elif _contiene(texto, [
        "ejecutá", "ejecuta", "hacé", "hace", "abrí", "abri", "mandá", "manda", "escribile", "enviá", "envia", "inicia", "iniciá"
        ]):
        return "ejecutar_tarea"

    elif ("borra" in texto or "olvida" in texto or "elimina" in texto) and ("todos" in texto or "toda" in texto) and ("recuerdos" in texto or "memoria" in texto):
        return "borrar_todos_los_recuerdos"

    elif "olvida que" in texto or "borra" in texto or "elimina" in texto:
        return "olvidar_recuerdo"

    elif ("record" in texto or "acord" in texto or "sabes" in texto or "recuerd" in texto) and "mi" in texto:
        return "leer_recuerdos"

    elif "record" in texto or "acordate" in texto or "no te olvides" in texto:
        return "guardar_recuerdo"

    elif _contiene(texto, [
        "abrí opera", "abre opera", "abrir opera", "inicia opera", "iniciar opera"
    ]):
        return "abrir_opera"

    elif _contiene(texto, [
        "qué hora", "que hora", "hora", "tenés la hora", "tienes la hora"
    ]):
        return "consultar_hora"

    elif _contiene(texto, [
        "cómo te llamas", "como te llamas", "cuál es tu nombre", "cual es tu nombre",
        "nombre", "quién sos", "quien sos"
    ]):
        return "consultar_nombre"

    elif _contiene(texto, [
    "hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"
    ]):
        if len(texto.split()) < 4:
            return "saludo"

    elif "uso" in texto:
        return "guardar_preferencia"

    elif "navegador" in texto:
        return "abrir_navegador"

    elif _contiene(texto, [
        "mirá mi pantalla", "mira mi pantalla", "mirá la pantalla", "mira la pantalla",
        "observá mi pantalla", "observa mi pantalla", "observá la pantalla",
        "qué ves en mi pantalla", "que ves en mi pantalla", "ves mi pantalla"
    ]):
        return "ver_pantalla"

    elif _contiene(texto, [
        "analiza mi proyecto", "analiza el proyecto", "analizá mi proyecto",
        "analiza /", "analizá /", "revisa el proyecto"
    ]):
        return "analizar_proyecto"

    elif _contiene(texto, [
        "analiza el archivo", "analiza el archivo", "analizá el archivo",
        "analiza /", "analizá /", "revisa el archivo"
    ]):
        return "analizar_archivo"

    elif _contiene(texto, [
        "solo errores", "solo seguridad", "solo optimizacion", "solo calidad",
        "solo errores de", "solo seguridad de", "busca errores", "busca vulnerabilidades"
    ]):
        return "analizar_con_filtro"
    
    elif any(frase in texto for frase in [
        "optimizá", "optimiza", "mejorá", "mejora", "refactorizá", "refactoriza", "buscá errores", "busca errores", "encontrá errores", "encontrar errores","corregí", "corrige", "arreglá", "arregla"
    ]):
        return "mejorar_codigo"

    elif any(indicador in texto for indicador in  ["/home/", "/tmp/", "~/", ".py", ".txt", ".md", ".json"]):
        return "leer_archivo"

    elif any(frase in texto for frase in [
        "auditá tu código", "audita tu código", "auditá tu codigo", "audita tu codigo",
        "auditoría", "auditoria", "auditate", "revisá todo tu código", "autoauditoría"
    ]):
        return "auditar_codigo"


    
    return "desconocida"

def extraer_recuerdo(texto):
    texto = texto.strip()

    frases_disparadoras = [
        "recordá que", 
        "recorda que", 
        "recuerdas que", 
        "te acordas de"
    ]

    texto_lower = texto.lower()

    for frase in frases_disparadoras:
        if frase in texto_lower: 
            inicio = texto_lower.find(frase) + len(frase) 
            recuerdo = texto[inicio:].strip(" ,¿?.,;:!")
            return recuerdo
    return None 

def extraer_olvido(texto):
    texto = texto.strip()
    texto_lower = texto.lower()

    frases_disparadoras = [
        "olvidate que",
        "olvida que",
        "olvidá qué",
        "olvida",
        "olvidá que",
        "olvidate de"
    ]

    for frase in frases_disparadoras: 
        if frase in texto_lower:
            inicio = texto_lower.find(frase) + len(frase)
            recuerdo = texto[inicio:].strip(" ,¿?.,;:!")
            return recuerdo
    return None

def extraer_preferencia(texto):
    texto = texto.lower().strip() 

    herramientas = ["navegador", "editor", "programa"]

    for herramienta in herramientas: 
        if herramienta in texto: 
            if "uso" in texto: 
                partes = texto.split("uso", 1)
                valor = partes[1].strip(" ,¿?.,;:!")
                return herramienta, valor
    return None, None

def extraer_objeto_apertura(texto):
    palabras = texto.split()

    disparadores = ["abrí", "abre", "abrir", "abri", "iniciá", "ejecutá"]

    for i, palabra in enumerate(palabras):
        if palabra in disparadores: 
            objeto = " ".join(palabras[i + 1:])
            return objeto.strip()
        
    return None

def clasificar_objeto_apertura(objeto):
    if not objeto:
        return None, None
    
    objeto = objeto.lower()

    categorias = ["navegador", "editor", "reproductor"]

    palabras = objeto.split()
    palabras_filtradas = [p for p in palabras if p not in ["el", "la", "los", "las"]]

    objeto_limpio = " ".join(palabras_filtradas)
    objeto_limpio = normalizar_nombre_programa(objeto_limpio)

    if objeto_limpio in categorias:
        return "categoria", objeto_limpio
    
    if objeto_limpio in ALIAS_PROGRAMAS:
        return "programa", objeto_limpio
    
    return None, None

def normalizar_nombre_programa(objeto):
    if not objeto:
        return None
    objeto = objeto.lower().strip()

    alias_programas = {
        "vs code": "vscode",
        "visual studio code": "vscode",
        "google chrome": "chrome",
        "bloc de notas": "notepad",
        "bloq de notas": "notepad",
        "notas": "notepad",
        "calculadora": "calc"
    }

    if objeto in alias_programas:
        return alias_programas[objeto]

    return objeto

def extraer_ruta_archivo(texto):
    """Extrae la ruta de un archivo del comando."""
    import re
    patron = r'(/[a-zA-Z0-9_\-./~]+\.py|/[a-zA-Z0-9_\-./~]+)'
    coincidencias = re.findall(patron, texto)
    if coincidencias:
        return coincidencias[0].strip()
    return None

def extraer_tipo_analisis(texto):
    """Extrae el tipo de análisis si se menciona específicamente."""
    texto_lower = texto.lower()

    if "solo errores" in texto_lower or "solo bugs" in texto_lower:
        return "errores"
    elif "solo seguridad" in texto_lower or "vulnerabilidades" in texto_lower:
        return "seguridad"
    elif "solo optimizacion" in texto_lower or "solo performance" in texto_lower:
        return "optimizacion"
    elif "solo calidad" in texto_lower or "solo estilo" in texto_lower:
        return "calidad"

    return "completo"


# --- Streaming + TTS por frases -------------------------------------------
# Sink opcional de voz: si está seteado (una función que consume un iterable de
# frases), consultar_llama va entregando cada frase TERMINADA a medida que el
# modelo la genera, para que el TTS empiece a hablar sin esperar la respuesta
# completa. La capa de UI lo instala con usar_sink_de_frases().
_frase_sink = None
# Marca si el último turno se resolvió por streaming (ya se habló en vivo), para
# que la UI no vuelva a reproducir la respuesta entera.
ULTIMO_TURNO_STREAMEADO = False

def usar_sink_de_frases(fn):
    """Registra (o limpia con None) el sink de voz por frases."""
    global _frase_sink
    _frase_sink = fn


def limpiar_para_tts(texto):
    """Saca marcado Markdown que no debería leerse en voz alta."""
    texto = re.sub(r'`+', '', texto)
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'#+\s*', '', texto)
    texto = re.sub(r'^\s*\d+\.\s+', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^\s*[-•]\s+', '', texto, flags=re.MULTILINE)
    return texto.strip()


_FIN_ORACION = re.compile(r'[.!?…]+["\'”’)\]]?\s+|\n+')

def _extraer_oraciones(buffer):
    """Corta oraciones COMPLETAS del buffer. Devuelve (oraciones, resto)."""
    oraciones = []
    ultimo = 0
    for m in _FIN_ORACION.finditer(buffer):
        oraciones.append(buffer[ultimo:m.end()])
        ultimo = m.end()
    return oraciones, buffer[ultimo:]


def frasear(tokens):
    """Agrupa un stream de fragmentos de texto en frases listas para hablar.
    Salta los bloques de código (```) y avisa una sola vez que hay código en
    pantalla, en vez de leerlo en voz alta."""
    buffer = ""
    en_codigo = False
    aviso_dado = False
    for tok in tokens:
        if not tok:
            continue
        buffer += tok
        while "```" in buffer:
            idx = buffer.find("```")
            if not en_codigo:
                oraciones, _ = _extraer_oraciones(buffer[:idx])
                for o in oraciones:
                    o = limpiar_para_tts(o)
                    if o:
                        yield o
                buffer = buffer[idx + 3:]
                en_codigo = True
                if not aviso_dado:
                    aviso_dado = True
                    yield "Revisá el código en pantalla."
            else:
                buffer = buffer[idx + 3:]
                en_codigo = False
        if en_codigo:
            buffer = buffer[-2:]  # dentro de código: nada que hablar (deja cola por ``` partido)
            continue
        oraciones, buffer = _extraer_oraciones(buffer)
        for o in oraciones:
            o = limpiar_para_tts(o)
            if o:
                yield o
    if not en_codigo:
        o = limpiar_para_tts(buffer)
        if o:
            yield o


def _preparar_sistema(texto, sesion):
    """Construye el system prompt (identidad + memoria + cerebro + contexto del
    proyecto) y agrega el turno del usuario al historial de la sesión.
    Devuelve el system prompt."""
    contexto_proyecto = _cargar_contexto_proyecto()  # cacheado, no toca disco cada turno
    if DEBUG_MODE:
        print(f"DEBUG CONTEXTO: {contexto_proyecto[:100] if contexto_proyecto else 'VACÍO'}")

    recuerdos = leer_recuerdos()
    contexto_memoria = "; ".join(recuerdos) if recuerdos else ""

    # Buscar recuerdos semánticos relevantes. Si ollama/embeddings falla, no
    # rompemos la respuesta entera: seguimos sin recuerdos semánticos.
    try:
        recuerdos_semanticos = recordar(texto[:500], top_k=3)
    except Exception as e:
        if DEBUG_MODE:
            print(f"DEBUG SEMANTICA FALLÓ: {e}")
        recuerdos_semanticos = []
    if DEBUG_MODE:
        print(f"DEBUG SEMANTICA: {[r['texto'][:40] for r in recuerdos_semanticos]}")
    if recuerdos_semanticos:
        contexto_semantico = "\n".join([f"- {r['texto']}" for r in recuerdos_semanticos])
        contexto_memoria = contexto_memoria + "\n\nRecuerdos relevantes para este momento:\n" + contexto_semantico if contexto_memoria else "Recuerdos relevantes para este momento:\n" + contexto_semantico

    # Buscar en el cerebro (vault de Obsidian) notas relevantes. También
    # blindado: un vault mal configurado no debe tumbar la conversación.
    try:
        notas_cerebro = cerebro.consultar_cerebro(texto, max_notas=3)
    except Exception as e:
        if DEBUG_MODE:
            print(f"DEBUG CEREBRO FALLÓ: {e}")
        notas_cerebro = []
    if DEBUG_MODE:
        print(f"DEBUG CEREBRO: {[n['titulo'] for n in notas_cerebro]}")

    # Armamos el system prompt base SIEMPRE (no depende de si hay memoria)
    sistema = (
        f"Sos {ASSISTANT_NAME}, un asistente personal creado por André. "
        "Naciste el 17 de abril de 2026. "
        "Respondés siempre en español salvo que se te indique otro idioma. "
        "Tu tono es tranquilo, directo y natural — como una persona inteligente charlando, no un manual. "
        "Nunca te presentés ni describas quién sos. Respondé directamente lo que te preguntan. "
        "Nunca menciones Llama, Meta ni tu modelo base. Si te preguntan quién te creó, decí solo 'André'. "
        "FORMATO: Máximo 2 párrafos cortos. Sin listas numeradas ni viñetas. Texto corrido siempre. "
        "Si un tema necesita enumerar cosas, incorporalas naturalmente en el texto separadas por comas."
    )

    # Agregamos lo que sabe del usuario, solo si hay algo
    if contexto_memoria:
        sistema += f"\n\nLo que sabés sobre el usuario:\n{contexto_memoria}"

    # Las notas del cerebro van con INSTRUCCIÓN EXPLÍCITA y bien separadas
    if notas_cerebro:
        contexto_notas = "\n\n".join(
            [f"### {n['titulo']}\n{n['contenido']}" for n in notas_cerebro]
        )
        sistema += (
            "\n\n=== NOTAS DE TU CEREBRO ===\n"
            "Las siguientes notas son TUYAS, escritas por vos y André. "
            "Son tu fuente principal de verdad sobre estos temas. "
            "Cuando respondas algo relacionado, basate en estas notas ANTES que en tu conocimiento general. "
            "Si una nota tiene información específica, usá esa información concreta en tu respuesta.\n\n"
            "IMPORTANTE: respondé directamente con la información, de forma natural."
            "NO digas 'recuerdo que', 'soy capaz de recordar', 'estoy familiarizado con'"
            "Simplemente respondé como si fuera conocimiento tuyo, directo.\n\n"
            + contexto_notas
        )

    if contexto_proyecto:
        sistema += f"\n\nContexto de tu arquitectura y proyecto:\n{contexto_proyecto}"

    sesion.historial.append({"role": "user", "content": texto})
    return sistema


def consultar_llama_stream(texto, sesion=None):
    """Consulta al LLM en modo streaming: cede los fragmentos de texto a medida
    que el modelo los genera. Actualiza el historial de la sesión y el dataset al
    terminar (incluso si el stream se corta a mitad)."""
    sesion = sesion or _sesion_default
    sistema = _preparar_sistema(texto, sesion)
    partes = []
    try:
        # Solo mandamos los últimos MAX_HISTORIAL mensajes: acota latencia, costo
        # y evita desbordar la ventana de contexto en charlas largas.
        stream = ollama.chat(
            model="dolphin3:8b",
            messages=[{"role": "system", "content": sistema}] + sesion.historial[-MAX_HISTORIAL:],
            stream=True,
        )
        for chunk in stream:
            parte = chunk["message"]["content"]
            if parte:
                partes.append(parte)
                yield parte
    finally:
        if partes:
            contenido = "".join(partes)
            sesion.historial.append({"role": "assistant", "content": contenido})
            if len(sesion.historial) > MAX_HISTORIAL:
                del sesion.historial[:-MAX_HISTORIAL]
            guardar_interaccion(texto, contenido)


def consultar_llama(texto, sesion=None):
    """Devuelve la respuesta completa como string (contrato original, usado por
    todo procesar_comando). Si hay un sink de voz activo, además va hablando por
    frases mientras el modelo genera, sin esperar la respuesta completa."""
    global ULTIMO_TURNO_STREAMEADO
    gen = consultar_llama_stream(texto, sesion)

    if _frase_sink is None:
        ULTIMO_TURNO_STREAMEADO = False
        return "".join(gen)

    partes = []
    def _captura():
        for t in gen:
            partes.append(t)
            yield t
    try:
        # el sink consume las frases (y con ellas el stream) hablando en pipeline
        _frase_sink(frasear(_captura()))
    finally:
        for _ in gen:  # garantiza agotar el generador (guarda historial/dataset)
            pass
    ULTIMO_TURNO_STREAMEADO = True
    return "".join(partes)

def leer_archivo(ruta):
    try: 
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e: 
        return None

def procesar_comando(texto, assistant_name, sesion=None):
    global ULTIMO_TURNO_STREAMEADO
    sesion = sesion or _sesion_default

    # arranca en False cada turno: solo consultar_llama con sink lo pone en True.
    # Así las respuestas determinísticas (hora, saludo, etc.) las habla la UI.
    ULTIMO_TURNO_STREAMEADO = False

    if DEBUG_MODE:
        print(f"DEBUG - ESPERANDO_TAREA: {sesion.esperando_confirmacion_tarea} | texto: {texto}")

    texto_original = texto

    if sesion.esperando_confirmacion_tarea:
        if DEBUG_MODE:
            print(f"DEBUG ENTRANDO A CONFIRMACION con texto: '{texto_original}'")

        if sesion.opciones_pendientes and texto_original.strip().lower() in ["a", "b", "c", "d"]:
            letras = ["a", "b", "c", "d"]
            indice = letras.index(texto_original.strip().lower())
            if indice < len(sesion.opciones_pendientes):
                nombre, comando = sesion.opciones_pendientes[indice]
                sesion.esperando_confirmacion_tarea = False
                sesion.opciones_pendientes.clear()
                if DEBUG_MODE:
                    print (f"DEBUG COMANDO: '{comando}'")
                    print (f"DEBUG ANTES DEL TRY")
                try:
                    proc = subprocess.Popen([comando], env=os.environ.copy())
                    if DEBUG_MODE:
                        print(f"DDEBUG PID: {proc.pid}")
                    return f"Ejecutando {nombre}..."
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"DEBUG ERROR: {type(e).__name__}: {e}")
                    return f"No pude abrir {nombre}."

        if texto_original.strip().lower().replace("í", "i") in ["si", "s", "yes", "y"]:
            sesion.esperando_confirmacion_tarea = False
            comando = ALIAS_PROGRAMAS.get(sesion.plan_pendiente, None)
            if not comando:
                comando = shutil.which(sesion.plan_pendiente)
            if not comando:
                primera_palabra = sesion.plan_pendiente.split()[0]
                comando = shutil.which(primera_palabra)
            if comando:
                try:
                    subprocess.Popen([comando], env=os.environ.copy())
                    return f"Ejecutando {sesion.plan_nombre}..."
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"DEBUG ERROR  KITTY: {type(e).__name__}: {e}")
                    return f"No pude abrir {sesion.plan_pendiente}."
            else:
                return f"No encontré {sesion.plan_pendiente} en el sistema."
        else:
            sesion.esperando_confirmacion_tarea = False
            sesion.plan_pendiente = ""
            return "Tarea cancelada."

    texto = normalizar_texto(texto)
    intencion = detectar_intencion(texto)

    if intencion == "ejecutar_tarea":
        verificacion = consultar_llama(f"¿El siguiente mensaje pide explícitamente abir o ejecutar una aplicación o programa? Respondé solo 'sí' o 'no'. Mensaje: '{texto_original}'", sesion)
        if "no" in verificacion.lower():
            return consultar_llama(texto_original, sesion)
        programa = extraer_programa_con_llama(texto_original)
        resultados = buscar_aplicaciones_sistema(programa)

        if len(resultados) == 0:
            return f"No encontré ninguna aplicación que coincida con '{programa}' en el sistema."

        elif len(resultados) == 1:
            nombre, comando = resultados[0]
            sesion.esperando_confirmacion_tarea = True
            sesion.plan_pendiente = comando
            sesion.plan_nombre = nombre
            return f"Encontré '{sesion.plan_nombre}'. ¿Lo abro?"

        else:
            letras = ["a", "b", "c", "d",]
            opciones_texto = "\n".join([f"{letras[i]}) {nombre}" for i, (nombre, comando) in enumerate(resultados)])
            sesion.opciones_pendientes = list(resultados)
            sesion.esperando_confirmacion_tarea = True
            sesion.plan_pendiente = ""
            return f"Encontré varias opciones:\n{opciones_texto}\n¿CUál querés abrir?"


    elif intencion == "borrar_todos_los_recuerdos":
        sesion.esperando_confirmacion_borrado = True
        return "¿Estás seguro? Escribí 'confirmar borrado, S/Y' para eleminar toda la memoria de forma permanente."

    elif intencion == "confirmar_borrado":
        if sesion.esperando_confirmacion_borrado:
            borrar_todos_los_recuerdos()
            sesion.esperando_confirmacion_borrado = False
            return "Todos los recuerdos han sido borrados."
        else:
            return "No hay ninguna acción de borrado pendiente de confirmación."

    elif intencion == "buscar_en_internet":
        consulta = extraer_consulta_busqueda(texto, assistant_name)

        if consulta:
            exito = buscar_en_internet(consulta)
            if exito:
                return f'Buscando "{consulta}" en internet...'
            return "No pude hacer la búsqueda."

        return "Decime qué querés buscar."

    elif intencion == "consultar_hora":
        ahora = datetime.datetime.now().strftime("%H:%M")
        return f"Son las {ahora}"

    elif intencion == "consultar_nombre":
        return f"Me llamo {assistant_name}"
    
    elif intencion == "auditar_codigo":
        print("Iniciando auto-auditoría. Esto puede tardar un par de minutos...")
        resultado = auditar_proyecto()
        return resultado


    elif intencion == "mejorar_codigo":
        if DEBUG_MODE:
            print("DEBUG: entrando a mejorar_codigo")
        rutas = re.findall(r'[~/][\w/\.\-]+', texto_original)
        if rutas:
            ruta = os.path.expanduser(rutas[0])
            contenido = leer_archivo(ruta)
            if contenido:
                codigo_mejorado = consultar_llama(f"Reescribí este código Python completo con mejoras. Tu respuesta debe empezar DIRECTAMENTE con 'import' o 'def' o '#'. CERO explicaciones, CERO texto antes o después del código:\n\n{contenido}", sesion)
                print(f"\n--- VERSIÓN DE DOLPHIN ---\n{codigo_mejorado}\n---")

                print("\nConsultando al revisor experto...")
                revision = revisar_codigo(codigo_mejorado, objetivo="revisar esta mejora y señalar errores o mejoras adicionales")
                if revision:
                    print(f"\n--- REVISIÓN DEL EXPERTO ---\n{revision}\n---")
                    guardar_par_entrenamiento(contenido, codigo_mejorado, revision)
                    print("(Par de entrenamiento guardado)")
                else:
                    print("\n(El revisor externo no está disponible, seguí con la versión de dolphin.)")

                confirmacion = input("¿Querés guardar la versión de dolphin? (si/no): ")
                if confirmacion.strip().lower() in ["si", "sí", "s", "yes"]:
                    escribir_archivo(ruta, codigo_mejorado)
                    return "Código guardado."
                return "Código no guardado."
            return f"No pude leer {ruta}."
        else:
            codigo_mejorado = consultar_llama(f"Mejorá este código. Devolvé ÚNICAMENTE el código mejorado:\n\n{texto_original}", sesion)
            print(f"\n--- CÓDIGO MEJORADO ---\n{codigo_mejorado}\n---")
            return "Revisá el código mejorado arriba."
    
    elif intencion == "guardar_en_cerebro":
        # Buscamos la última cosa que dijo Bridget en el historial.
        # Recorremos de atrás para adelante hasta encontrar un mensaje del asistente.
        ultima_respuesta = None
        for mensaje in reversed(sesion.historial):
            if mensaje["role"] == "assistant":
                ultima_respuesta = mensaje["content"]
                break

        if not ultima_respuesta:
            return "No tengo nada reciente para guardar todavía. Decime algo primero y después pedime que lo guarde."

        # Clasificamos la nota: en una sola llamada al LLM obtenemos
        # título, categoría (carpeta) y tags. Reemplaza a generar_titulo.
        clasificacion = cerebro.clasificar_nota(ultima_respuesta, lambda p: consultar_llama(p, sesion))
        titulo = clasificacion["titulo"]
        categoria = clasificacion["categoria"]
        tags = clasificacion["tags"]

        ruta = cerebro.guardar_nota(
            titulo=titulo,
            contenido=ultima_respuesta,
            carpeta=categoria,      # la categoría decide la subcarpeta
            tags=tags
        )
        if ruta:
            # armamos un mensaje que muestra dónde y cómo lo guardó
            texto_tags = (" con tags " + ", ".join(tags)) if tags else ""
            return f"Guardado en «{categoria}» como «{titulo}»{texto_tags}."
        else:
            return "Quise guardarlo pero algo falló al escribir la nota."

    elif intencion == "guardar_recuerdo":
        recuerdo = extraer_recuerdo(texto) 

        if recuerdo: 
            guardado = guardar_recuerdo(recuerdo)

            if guardado:
                return f"Listo, voy a recordar que {recuerdo}."
            
            else: 
                return f"Eso ya lo recordaba: {recuerdo}." 
            
        return "No entendí qué querés que recuerde."
    
    elif intencion == "leer_recuerdos":
        recuerdos = leer_recuerdos()

        if recuerdos: 
            recuerdos_texto = "; ".join(recuerdos)
            return f"Esto recuerdo de vos: {recuerdos_texto}"
        return "Todavía no tengo recuerdos guardados sobre vos."

    elif intencion == "saludo":
        return "Hola, ¿cómo estás?"
    
    elif intencion == "olvidar_recuerdo":
        recuerdo = extraer_olvido(texto)

        if recuerdo: 
            olvidado = olvidar_recuerdo(recuerdo)
            
            if olvidado: 
                return f"Listo, ya no voy a recordar que {recuerdo}."
            else: 
                return f"No encontré ese recuerdo: {recuerdo}."
            
        return "No entendí qué querés que olvide."
    
    elif intencion == "guardar_preferencia":
        tipo, valor = extraer_preferencia(texto)

        if tipo and valor:
            guardar_preferencia(tipo, valor)
            return f"Perfecto, voy a usar {valor} como {tipo}."
        
        return "No entendí la preferencia."

    elif intencion == "ver_pantalla":
        descripcion = ver_pantalla()
        return consultar_llama(f"Estoy viendo esto en mi pantalla: {descripcion}. Ayudame en base a eso.", sesion)

    elif intencion == "buscar_web":
        resultados = buscar_web(texto_original)
        contexto = formatear_resultados(resultados)
        return consultar_llama(f"El usuario preguntó: {texto_original}\n\nEncontré esta información en internet:\n{contexto}\n\nRespondé de forma concisa en 2-3 oraciones basándote en esa información.", sesion)

    elif intencion == "analizar_archivo":
        ruta = extraer_ruta_archivo(texto_original)
        tipo_analisis = extraer_tipo_analisis(texto_original)

        if not ruta:
            return "Necesito que me indiques la ruta del archivo. Ejemplo: 'analiza /ruta/del/archivo.py'"

        if not os.path.exists(ruta):
            return f"No encontré el archivo en: {ruta}"

        resultado = analizar_archivo(ruta, tipo_analisis)

        if not resultado:
            return f"No pude analizar el archivo: {ruta}"

        ruta_reporte = guardar_reporte(resultado, formato="markdown", tipo="archivo")
        return f"Análisis completado. Reporte guardado en: {ruta_reporte}\n\n{resultado['analisis']}"

    elif intencion == "analizar_proyecto":
        ruta = extraer_ruta_archivo(texto_original)
        tipo_analisis = extraer_tipo_analisis(texto_original)

        if not ruta:
            return "Necesito que me indiques la ruta del proyecto. Ejemplo: 'analiza mi proyecto /ruta/del/proyecto'"

        if not os.path.isdir(ruta):
            return f"No encontré la carpeta en: {ruta}"

        resultado = analizar_proyecto(ruta, tipo_analisis)

        if not resultado:
            return f"No encontré archivos Python en: {ruta}"

        ruta_reporte = guardar_reporte(resultado, formato="markdown", tipo="proyecto")
        return f"Análisis del proyecto completado. Reporte guardado en: {ruta_reporte}\nArchivos analizados: {resultado['archivos_analizados']}"

    elif intencion == "analizar_con_filtro":
        ruta = extraer_ruta_archivo(texto_original)
        tipo_analisis = extraer_tipo_analisis(texto_original)

        if not ruta:
            return "Necesito que me indiques el archivo o proyecto. Ejemplo: 'solo errores de /ruta/archivo.py'"

        if os.path.isfile(ruta):
            resultado = analizar_archivo(ruta, tipo_analisis)
            ruta_reporte = guardar_reporte(resultado, formato="markdown", tipo="archivo")
            return f"Análisis de {tipo_analisis} completado.\nReporte: {ruta_reporte}\n\n{resultado['analisis']}"
        elif os.path.isdir(ruta):
            resultado = analizar_proyecto(ruta, tipo_analisis)
            ruta_reporte = guardar_reporte(resultado, formato="markdown", tipo="proyecto")
            return f"Análisis del proyecto completado. Reporte guardado en: {ruta_reporte}"
        else:
            return f"No encontré archivo o carpeta en: {ruta}"
    
    elif intencion == "leer_archivo":
        rutas = re.findall(r'[~/][\w/\.\-]+', texto_original)
        if rutas:
            ruta = os.path.expanduser(rutas[0])
            contenido = leer_archivo(ruta)
            if contenido:
                return consultar_llama(f"El usuario te pidió: {texto_original}\n\nContenido del archivo:\n{contenido}", sesion)
            else:
                return f"No pude leer el archivo {ruta}."
        return "No encontré ninguna ruta de archivo en tu mensaje."

    respuesta = consultar_llama(texto_original, sesion)
    if respuesta:
        return respuesta

    return "no pude generar una respuesta"

def escribir_archivo(ruta, contenido):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        return True
    except Exception:
        return False
