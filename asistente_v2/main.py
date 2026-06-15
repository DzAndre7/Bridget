import datetime 
from core.brain import procesar_comando, consultar_llama
from core.memory import obtener_nombre_preferido, guardar_recuerdo
from core.voice import hablar, hablar_interrumpible
from core.listen import escuchar

ASSISTANT_NAME = "Rick"
VOZ_ACTIVADA = True

def limpiar_para_tts(texto):
    import re
    texto = re.sub(r'\*+', '', texto)  # quita asteriscos
    texto = re.sub(r'^\d+\.\s', '', texto, flags=re.MULTILINE)  # quita numeración
    texto = re.sub(r'^[-•]\s', '', texto, flags=re.MULTILINE)  # quita viñetas
    texto = re.sub(r'`+', '', texto)  # quita comillas de código
    return texto.strip()

def obtener_saludo(): 
    hora = datetime.datetime.now().hour 

    if 5 <= hora < 12:
        return "Buenos días, estoy listo para arrancar."

    elif 12 <= hora < 18:
        return "Buenas tardes, listo cuando vos quieras."

    else: 
        return "Buenas noches, decime qué hacemos hoy."

def modo_voz():
    print(f"{ASSISTANT_NAME}: Modo voz activado. Decí 'salir del modo voz' pàra volver.")
    hablar("Modo voz activado. Te escucho.")

    while True:
        texto = escuchar()

        if not texto or not texto.strip():
            continue

        nombre_usuario = obtener_nombre_preferido() or "Usuario"
        print(f"{nombre_usuario} (voz): {texto}")

        texto_lower = texto.lower()
        if "salir" in texto_lower and ("voz" in texto_lower or "boss" in texto_lower or "modo" in texto_lower):
            hablar("Saliendo del modo voz.")
            print(f"{ASSISTANT_NAME}: Modo voz desactivado.")
            break

        respuesta = procesar_comando(texto, ASSISTANT_NAME)
        print(f"{ASSISTANT_NAME}: {respuesta}")

        if "```" in respuesta:
            hablar("Revisá el código en pantalla.")
        else:
            hablar(limpiar_para_tts(respuesta))

import threading 

def modo_voz_interrumpible():
    from core.listen import escuchar_fragmento
    print(f"{ASSISTANT_NAME}: Modo voz activado. Decí 'salir del modo voz' para volver.")
    hablar("Modo voz activado. Te escucho.")

    while True:
        texto = escuchar()

        if not texto or not texto.strip():
            continue

        nombre_usuario = obtener_nombre_preferido() or "Usuario"
        print(f"{nombre_usuario} (voz): {texto}")

        texto_lower = texto.lower()
        if "salir" in texto_lower and ("voz" in texto_lower or "boss" in texto_lower or "modo" in texto_lower):
            hablar("Saliendo del modo voz.")
            print(f"{ASSISTANT_NAME}: Modo voz desactivado.")
            break

        respuesta = procesar_comando(texto, ASSISTANT_NAME)
        print(f"{ASSISTANT_NAME}: {respuesta}")

        if "```" in respuesta:
            hablar("Revisá el código en pantalla.")
            continue

        # --- Reprocucción interrumpible ---
        interrumpido = threading.Event()

        def vigilar_interrupcion():
            while not interrumpido.is_set():
                fragmento = escuchar_fragmento(1.0)
                if any(palabra in fragmento for palabra in ["para", "pará", "pera", "par", "pala", "stop", "basta", "callate", "calla"]):
                    interrumpido.set()
                    break
        
        proceso_audio = hablar_interrumpible(limpiar_para_tts(respuesta))

        hilo_vigilancia = threading.Thread(target=vigilar_interrupcion, daemon=True)
        hilo_vigilancia.start()

        while proceso_audio.poll() is None: 
            if interrumpido.is_set():
                proceso_audio.terminate()
                hablar("¿Qué pasó? Te escucho...")
                break
        
        interrumpido.set() 
        hilo_vigilancia.join(timeout=0.5)

def main():
    saludo = obtener_saludo()
    print(f"{ASSISTANT_NAME}: {saludo}")   

    while True: 
        nombre_usuario = obtener_nombre_preferido() or "André"
        user_input = input(f"{nombre_usuario}: ")

        if user_input.lower().strip() == "escuchame": 
            user_input = escuchar()
            print(f"{nombre_usuario} (voz): {user_input}")

        if user_input.lower().strip() in ["modo voz", "modo audio", "manos libres"]:
            modo_voz_interrumpible()
            continue

        if user_input.lower().strip() in ["activar voz", "activá voz", "modo texto", "silencio", "callate"]:
            global VOZ_ACTIVADA
            VOZ_ACTIVADA = not VOZ_ACTIVADA
            estado = "activada" if VOZ_ACTIVADA else "desactivada"
            print(f"{ASSISTANT_NAME}: Voz {estado}.")
            continue

        if user_input.lower() in ["salir", "exit", "quit", "adiós", "adios"]:
            print(f"{ASSISTANT_NAME}: Nos vemos.")
            break

        elif user_input.lower() in ["cerrar", "fin sesion", "fin sesión"]:
            resumen = consultar_llama("Hacé un resumen breve de los temas importantes que hablamos en esta sesión. Si no hablamos de nada relevante, decilo.")
            print(f"{ASSISTANT_NAME}: {resumen}")
            hablar(resumen)
            confirmacion = input("Querés guardar este resumen en la memoria? (si/no): ")
            if confirmacion.strip().lower() in ["si", "sí", "s", "yes"]:
                guardar_recuerdo(resumen)
                print(f"{ASSISTANT_NAME}: Resumen guardado.")
            print(f"{ASSISTANT_NAME}: Nos vemos.")
            break

        respuesta = procesar_comando(user_input, ASSISTANT_NAME)   
        if respuesta is None:
            respuesta = "No pude generar una respuesta."
        print(f"{ASSISTANT_NAME}: {respuesta}") 
        if VOZ_ACTIVADA:
            if "```" in respuesta:
                hablar("Revisá el código en pantalla.")
            else:
                hablar(limpiar_para_tts(respuesta))  

if __name__ == "__main__":
    main()