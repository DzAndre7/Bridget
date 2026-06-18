import datetime
import unicodedata
import ollama
import subprocess
import shutil
import os

from core.memoria_semantica import recordar, guardar_recuerdo as guardar_recuerdo_semantico
from actions.system_actions import buscar_en_internet, abrir_programa, PROGRAMAS
from core.memory import cargar_recuerdos, guardar_recuerdo, leer_recuerdos, olvidar_recuerdo, borrar_todos_los_recuerdos
from core.preferences import cargar_preferencias, guardar_preferencia, obtener_preferencia
from core.vision import ver_pantalla
from actions.agent_actions import planificar_tarea, extraer_programa_con_llama, ALIAS_PROGRAMAS, buscar_aplicaciones_sistema
from core.search import buscar_web, formatear_resultados
from core.code_analyzer import analizar_archivo, analizar_proyecto, guardar_reporte
from core.dataset_collector import guardar_interaccion 
from core.code_reviewer import revisar_codigo
from core.auditoria import auditar_proyecto

HISTORIAL_CONVERSACION =  []
OPCIONES_PENDIENTES = []
ESPERANDO_CONFIRMACION_BORRADO = False
ESPERANDO_CONFIRMACION_TAREA = False
PLAN_PENDIENTE = ""
PLAN_NOMBRE = ""
DEBUG_MODE = True

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

    palabras_a_sacar = [
        "buscar", "busca", "buscá", "buscame", "búscame",
        "encontrar", "encontra", "encontrá",
        "averiguar", "averigua", "averiguá",
        "internet", "google", "web", "online",
    ]

    palabras = texto.split()
    consulta_limpia = []

    for palabra in palabras:
        palabra_limpia = palabra.strip(" ,¿?.,;:!").lower()

        if palabra_limpia not in palabras_a_sacar:
            consulta_limpia.append(palabra.strip(" ,¿?.,;:!"))

            consulta = " ".join(consulta_limpia).strip()
            consulta = " ".join(consulta.split())

            for sufijo in [" en la", " en el", " en"]: 
                if consulta.endswith(sufijo):
                    consulta = consulta[:-len(sufijo)].strip()

    return consulta if consulta else None

def detectar_intencion(texto):
    texto = texto.lower().strip()

    if any(frase in texto for frase in [
        "busca en internet", "buscá en internet", "busca online", "modo conectado", "busca en la web"
    ]):
        return "buscar_web"

    elif es_intencion_busqueda(texto):
        return "buscar_en_internet"
    
    elif texto in ["s", "y", "confirmar borrado"]:
        return "confirmar_borrado"
    
    elif any(frase in texto for frase in [
        "ejecutá", "ejecuta", "hacé", "hace", "abrí", "abri", "mandá", "manda", "escribile", "enviá", "envia", "inicia", "iniciá"
        ]):
        return "ejecutar_tarea"

  #  elif any(frase in texto for frase in [
  #     "analizá", "analiza", "analizame", "revisá", "revisa", "buscá bugs", "busca bugs"
  #  ]):
  #      return "analizar_codigo"
    
    
    elif ("borra" in texto or "olvida" in texto or "elimina" in texto) and ("todos" in texto or "toda" in texto) and ("recuerdos" in texto or "memoria" in texto):
        return "borrar_todos_los_recuerdos"
    
    elif "olvida que" in texto or "borra" in texto or "elimina" in texto: 
        return "olvidar_recuerdo"
    
    elif ("record" in texto or "acord" in texto or "sabes" in texto or "recuerd" in texto) and "mi" in texto:
        return "leer_recuerdos"
    
    elif "record" in texto or "acordate" in texto or "no te olvides" in texto:
        return "guardar_recuerdo"

    elif any(frase in texto for frase in [
        "abrí opera", "abre opera", "abrir opera", "inicia opera", "iniciar opera"
    ]):
        return "abrir_opera"

    elif any(frase in texto for frase in [
        "qué hora", "que hora", "hora", "tenés la hora", "tienes la hora"
    ]):
        return "consultar_hora"

    elif any(frase in texto for frase in [
        "cómo te llamas", "como te llamas", "cuál es tu nombre", "cual es tu nombre",
        "nombre", "quién sos", "quien sos"
    ]):
        return "consultar_nombre"
    
    elif any(frase in texto for frase in [
    "hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"
    ]):
        if len(texto.split()) < 4:
            return "saludo"
    
    elif "uso" in texto: 
        return "guardar_preferencia"
    
    elif "navegador" in texto:
        return "abrir_navegador"

    elif any(frase in texto for frase in [
        "mirá mi pantalla", "mira mi pantalla", "mirá la pantalla", "mira la pantalla",
        "observá mi pantalla", "observa mi pantalla", "observá la pantalla",
        "qué ves en mi pantalla", "que ves en mi pantalla", "ves mi pantalla"
    ]):
        return "ver_pantalla"

    elif any(frase in texto for frase in [
        "analiza mi proyecto", "analiza el proyecto", "analizá mi proyecto",
        "analiza /", "analizá /", "revisa el proyecto"
    ]):
        return "analizar_proyecto"

    elif any(frase in texto for frase in [
        "analiza el archivo", "analiza el archivo", "analizá el archivo",
        "analiza /", "analizá /", "revisa el archivo"
    ]):
        return "analizar_archivo"

    elif any(frase in texto for frase in [
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
    
    if objeto_limpio in PROGRAMAS:
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


def consultar_llama(texto):
    global HISTORIAL_CONVERSACION
    contexto_proyecto = "" 
    ruta_contexto = os.path.join(os.path.dirname(__file__), "..", "context.md")
    try: 
        with open(ruta_contexto, "r", encoding="utf-8") as f: 
            contexto_proyecto = f.read()
    except: 
        pass
    if DEBUG_MODE:
        print(f"DEBUG CONTEXTO: {contexto_proyecto[:100]if contexto_proyecto else 'VACÍO'}")
    recuerdos = leer_recuerdos()
    contexto_memoria = "; ".join(recuerdos) if recuerdos else ""

    # Buscar recuerdos semánticos relevantes para el momento actual
    recuerdos_semanticos = recordar(texto, top_k=3)
    if DEBUG_MODE: 
        print(f"DEBUG SEMANTICA: {[r['texto'][:40] for r in recuerdos_semanticos]}")
    if recuerdos_semanticos:
        contexto_semantico = "\n".join([f"- {r['texto']}" for r in recuerdos_semanticos])
        contexto_memoria = contexto_memoria + "\n\nRecuerdos relevantes para este momento:\n" + contexto_semantico if contexto_memoria else "Recuerdos relevantes para este momento:\n" + contexto_semantico

    sistema = (
    "Sos Rick, un asistente personal creado por André. "
    "Naciste el 17 de abril de 2026. "
    "Respondés siempre en español salvo que se te indique otro idioma. "
    "Tu tono es tranquilo, directo y natural — como una persona inteligente charlando, no un manual. "
    "Nunca te presentés ni describas quién sos. Respondé directamente lo que te preguntan. "
    "Nunca menciones Llama, Meta ni tu modelo base. Si te preguntan quién te creó, decí solo 'André'. "
    "FORMATO: Máximo 2 párrafos cortos. Sin listas numeradas ni viñetas. Texto corrido siempre. "
    "Si un tema necesita enumerar cosas, incorporalas naturalmente en el texto separadas por comas. "
    f"Lo que sabés sobre el usuario: {contexto_memoria}" if contexto_memoria else ""
    )
    if contexto_proyecto: 
        sistema += f"\n\nContexto de tu arquitectura y proyecto: \n{contexto_proyecto}"

    HISTORIAL_CONVERSACION.append({"role": "user", "content": texto})   

    respuesta = ollama.chat(
        model="dolphin3:8b",
        messages=[{"role": "system", "content": sistema}] + HISTORIAL_CONVERSACION  
    )
    contenido = respuesta["message"]["content"]
    HISTORIAL_CONVERSACION.append({"role": "assistant", "content": contenido})  
    guardar_interaccion(texto, contenido)
    return contenido

def leer_archivo(ruta):
    try: 
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e: 
        return None

def procesar_comando(texto, assistant_name):

    global ESPERANDO_CONFIRMACION_BORRADO
    global ESPERANDO_CONFIRMACION_TAREA
    global PLAN_PENDIENTE
    global OPCIONES_PENDIENTES
    global  PLAN_NOMBRE

    if DEBUG_MODE: 
        print(f"DEBUG - ESPERANDO_TAREA: {ESPERANDO_CONFIRMACION_TAREA} | texto: {texto}")

    texto_original = texto 

    if ESPERANDO_CONFIRMACION_TAREA:
        if DEBUG_MODE:
            print(f"DEBUG ENTRANDO A CONFIRMACION con texto: '{texto_original}'")

        if OPCIONES_PENDIENTES and texto_original.strip().lower() in ["a", "b", "c", "d"]:
            letras = ["a", "b", "c", "d"]
            indice = letras.index(texto_original.strip().lower())
            if indice < len(OPCIONES_PENDIENTES):
                nombre, comando = OPCIONES_PENDIENTES[indice]
                ESPERANDO_CONFIRMACION_TAREA = False
                OPCIONES_PENDIENTES.clear()
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
            ESPERANDO_CONFIRMACION_TAREA = False
            comando = ALIAS_PROGRAMAS.get(PLAN_PENDIENTE, None)
            if not comando:
                comando = shutil.which(PLAN_PENDIENTE)
            if not comando:
                primera_palabra = PLAN_PENDIENTE.split()[0]
                comando = shutil.which(primera_palabra)
            if comando:
                try:
                    subprocess.Popen([comando], env=os.environ.copy())
                    return f"Ejecutando {PLAN_NOMBRE}..."
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"DEBUG ERROR  KITTY: {type(e).__name__}: {e}")
                    return f"No pude abrir {PLAN_PENDIENTE}."
            else:
                return f"No encontré {PLAN_PENDIENTE} en el sistema."
        else:
            ESPERANDO_CONFIRMACION_TAREA = False
            PLAN_PENDIENTE = ""
            return "Tarea cancelada."

    texto = normalizar_texto(texto)
    intencion = detectar_intencion(texto)

    if intencion == "ejecutar_tarea":
        verificacion = consultar_llama(f"¿El siguiente mensaje pide explícitamente abir o ejecutar una aplicación o programa? Respondé solo 'sí' o 'no'. Mensaje: '{texto_original}'")
        if "no" in verificacion.lower():
            return consultar_llama(texto_original)
        programa = extraer_programa_con_llama(texto_original)
        resultados = buscar_aplicaciones_sistema(programa)
        
        if len(resultados) == 0:
            return f"No encontré ninguna aplicación que coincida con '{programa}' en el sistema."
    
        elif len(resultados) == 1:
            nombre, comando = resultados[0]
            ESPERANDO_CONFIRMACION_TAREA = True
            PLAN_PENDIENTE = comando
            PLAN_NOMBRE = nombre
            return f"Encontré '{PLAN_NOMBRE}'. ¿Lo abro?"
    
        else:
            letras = ["a", "b", "c", "d",]
            opciones_texto = "\n".join([f"{letras[i]}) {nombre}" for i, (nombre, comando) in enumerate(resultados)])
            OPCIONES_PENDIENTES = resultados
            ESPERANDO_CONFIRMACION_TAREA = True
            PLAN_PENDIENTE = "" 
            return f"Encontré varias opciones:\n{opciones_texto}\n¿CUál querés abrir?"


    elif intencion == "borrar_todos_los_recuerdos":
        ESPERANDO_CONFIRMACION_BORRADO = True
        return "¿Estás seguro? Escribí 'confirmar borrado, S/Y' para eleminar toda la memoria de forma permanente."
    
    elif intencion == "confirmar_borrado":
        if ESPERANDO_CONFIRMACION_BORRADO:
            borrar_todos_los_recuerdos()
            ESPERANDO_CONFIRMACION_BORRADO = False
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

    elif intencion == "abrir":
        objeto = extraer_objeto_apertura(texto)
        tipo, valor = clasificar_objeto_apertura(objeto)

        if tipo == "categoria":
            programa = obtener_preferencia(valor)

            if programa:
                abrir_programa(programa)
                return f"Abriendo {programa}..."
            else:
                return f"No sé qué {valor} usar todavía."
            
        elif tipo == "programa":
            exito = abrir_programa(valor)

            if exito: 
                return f"Abriendo {valor}..."
            else:
                return f"Entendí que querías abrir {valor}, pero no pude ejecutarlo."

        return "Entendí que querías abrir algo, pero no reconocí qué programa o categría era."

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
        import re 
        rutas = re.findall(r'[~/][\w/\.\-]+', texto_original)
        if rutas: 
            ruta = rutas[0].replace("~", "/home/bridget")
            contenido = leer_archivo(ruta)
            if contenido:
                codigo_mejorado = consultar_llama(f"Reescribí este código Python completo con mejoras. Tu respuesta debe empezar DIRECTAMENTE con 'import' o 'def' o '#'. CERO explicaciones, CERO texto antes o después del código:\n\n{contenido}")
                print(f"\n--- VERSIÓN DE DOLPHIN ---\n{codigo_mejorado}\n---")

                print("\nConsultando al revisor experto...")
                revision = revisar_codigo(codigo_mejorado, objetivo="revisar esta mejora y señalar errores o mejoras adicionales")
                if revision:
                    print(f"\n--- REVISIÓN DEL EXPERTO ---\n{revision}\n---")
                else:
                    print("\n(El revisor externo no está disponible, seguí con la versión de dolphin.)")

                confirmacion = input("¿Querés guardar la versión de dolphin? (si/no): ")
                if confirmacion.strip().lower() in ["si", "sí", "s", "yes"]:
                    escribir_archivo(ruta, codigo_mejorado)
                    return "Código guardado."
                return "Código no guardado."
            return f"No pude leer {ruta}."
        else: 
            codigo_mejorado = consultar_llama(f"Mejorá este código. Devolvé ÚNICAMENTE el código mejorado:\n\n{texto_original}")
            print(f"\n--- CÓDIGO MEJORADO ---\n{codigo_mejorado}\n---")
            return "Revisá el código mejorado arriba."
    
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
        return consultar_llama(f"Estoy viendo esto en mi pantalla: {descripcion}. Ayudame en base a eso.")

    elif intencion == "buscar_web":
        resultados = buscar_web(texto_original)
        contexto = formatear_resultados(resultados)
        return consultar_llama(f"El usuario preguntó: {texto_original}\n\nEncontré esta información en internet:\n{contexto}\n\nRespondé de forma concisa en 2-3 oraciones basándote en esa información.")

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
        import re 
        rutas = re.findall(r'[~/][\w/\.\-]+', texto_original)
        if rutas:
            ruta = rutas[0].replace("~", "/home/bridget")
            contenido = leer_archivo(ruta)
            if contenido:
                return consultar_llama(f"El usuario te pidió: {texto_original}\n\nContenido del archivo:\n{contenido}")
            else: 
                return f"No pude leer el archivo {ruta}."
        return "No encontré ninguna ruta de archivo en tu mensaje."
    respuesta = consultar_llama(texto_original)
    if respuesta: 
        return respuesta
    
    
    return "no pude generar una respuesta"

def escribir_archivo(ruta, contenido):
    try: 
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
    except Exception as e: 
        return False


    return consultar_llama(texto_original)
