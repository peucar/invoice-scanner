import os
import sys
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, command, process):
        self.command = command
        self.process = process
        self.cooldown = 0

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            now = time.time()
            if now - self.cooldown > 1: # Prevenir multiples triggers por 1 guardado
                print(f"\n[DEV] Detectado cambio en: {os.path.basename(event.src_path)}")
                print("[DEV] Reiniciando aplicación...")
                self.restart_app()
                self.cooldown = now

    def restart_app(self):
        if self.process.poll() is None:
            try:
                # En Windows, a veces terminate() no basta para Tkinter
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], capture_output=True)
            except Exception:
                self.process.terminate()
            self.process.wait()
        
        # Iniciar nuevo proceso
        print("[DEV] Lanzando nueva instancia...")
        self.process = subprocess.Popen(self.command)

if __name__ == "__main__":
    print("="*60)
    print(" 🛠️  MODO DESARROLLO: HOT RELOAD ACTIVADO")
    print(" 📝  Guarda cualquier archivo (.py) para recargar la app al instante")
    print("="*60)

    # Comando para iniciar la app real
    app_command = ["py", "main.py"]
    
    # Iniciar la primera vez
    current_process = subprocess.Popen(app_command)
    
    event_handler = ChangeHandler(app_command, current_process)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            # Si el proceso terminó (porque el usuario cerró la ventana), matamos el watcher
            if current_process.poll() is not None:
                 break
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        if current_process.poll() is None:
            current_process.terminate()
