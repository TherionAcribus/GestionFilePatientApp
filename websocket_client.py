import socketio
import json
import time
from PySide6.QtCore import Signal, QThread


class WebSocketClient(QThread):
    signal_print = Signal(str)

    def __init__(self, web_url):
        super().__init__()
        if "https" in web_url:
            self.web_url = web_url.replace("https", "wss")
        else:
            self.web_url = web_url.replace("http", "ws")

        self._should_run = True
        self._is_connected = False
        
        # Configuration du client avec reconnexion désactivée par défaut
        self.sio = socketio.Client(
            logger=True,
            engineio_logger=True,
            reconnection=False  # Désactive la reconnexion automatique
        )

        # Connexion aux événements WebSocket
        self.sio.on('connect', self.on_connect, namespace='/socket_app_patient')
        self.sio.on('disconnect', self.on_disconnect, namespace='/socket_app_patient')
        self.sio.on('update', self.on_update, namespace='/socket_app_patient')

    def run(self):
        self._should_run = True
        while self._should_run:
            try:
                if not self._is_connected:
                    self.sio.connect(
                        self.web_url,
                        namespaces=['/socket_app_patient'],
                        wait_timeout=10,
                        transports=['websocket']  # Force l'utilisation de WebSocket uniquement
                    )
                    self._is_connected = True
                
                # Attendre tant que la connexion est active
                while self._is_connected and self._should_run:
                    self.sio.sleep(1)
                
                # Si on sort de la boucle et qu'on ne devrait plus tourner, on sort
                if not self._should_run:
                    break

            except socketio.exceptions.ConnectionError as e:
                print(f"Erreur de connexion: {e}")
                if not self._should_run:
                    break
                time.sleep(5)
            except Exception as e:
                print(f"Erreur inattendue: {e}")
                break
        
        # Nettoyage final
        self._cleanup()

    def stop(self):
        """Arrête proprement le client WebSocket"""
        print("Arrêt du client WebSocket...")
        self._should_run = False
        self._is_connected = False
        self._cleanup()
        self.quit()
        self.wait()
        print("Client WebSocket arrêté")

    def _cleanup(self):
        """Nettoyage des ressources"""
        try:
            if hasattr(self, 'sio') and self.sio.connected:
                self.sio.disconnect()
        except Exception as e:
            print(f"Erreur lors du nettoyage: {e}")

    def on_connect(self):
        print('WebSocket connecté')
        self._is_connected = True

    def on_disconnect(self):
        print('WebSocket déconnecté')
        self._is_connected = False
        if not self._should_run:
            self.quit()

    def on_update(self, data):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            print(f"Mise à jour reçue: {data}")
            if data.get('flag') == 'print':
                self.signal_print.emit(data['data'])
        except json.JSONDecodeError as e:
            print(f"Erreur de décodage JSON: {e}")