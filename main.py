from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QVBoxLayout, QWidget, 
                                QLineEdit, QPushButton, QDialog, QLabel, QFormLayout, 
                                QMenuBar, QMessageBox, QHBoxLayout)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import Qt, QSettings, QThread, Signal, QObject, QEvent
from PySide6.QtGui import QAction
from requests.exceptions import RequestException
import requests
import json
import time
import sys
import os

import print_functions
from websocket_client import WebSocketClient

default_unlockpass = "aa"


class SSEClient(QThread):
    sse_print = Signal(object)

    def run(self):
        print("Connecting to SSE server...")
        while True:
            try:
                web_url = self.parent().web_url
                # Using 'with' to ensure the connection is properly managed
                with requests.get(f'{web_url}/events/update_patient_app', stream=True) as response:
                    client = response.iter_lines()
                    for line in client:
                        if line:
                            print("LINE", line)
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                json_data = decoded_line[5:].strip()
                                data = json.loads(json_data)
                                if data['type'] == 'print':
                                    print("Emitting signal with message:", data['message'])
                                    self.sse_print.emit(data['message'])
            except RequestException as e:
                print(f"Connection lost: {e}")
                time.sleep(5)  # Wait for 5 seconds before attempting to reconnect
                print("Attempting to reconnect...")

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                time.sleep(5)  # Wait for 5 seconds before attempting to reconnect

            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(5)  # Wait for 5 seconds before attempting to reconnect

def resource_path(relative_path):
    """ Obtenez le chemin d'accès absolu aux ressources pour le mode PyInstaller. """
    try:
        # PyInstaller crée un dossier temporaire et y stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")

        self.main_layout = QVBoxLayout(self)

        self.secret_input = QLineEdit(self)
        form_layout = QFormLayout()
        form_layout.addRow("Mot pour débloquer le plein écran:", self.secret_input)

        self.web_url_input = QLineEdit(self)
        form_layout.addRow("URL de la page web:", self.web_url_input)

        self.save_button = QPushButton("Enregistrer", self)
        self.save_button.clicked.connect(self.save_preferences)

        self.main_layout.addLayout(form_layout)
        self.main_layout.addWidget(self.save_button)

        self.setLayout(self.main_layout)
    
    def load_preferences(self):
        settings = QSettings()
        self.web_url_input.setText(settings.value("web_url", "http://localhost:5000"))
        self.secret_input.setText(settings.value("unlockpass", default_unlockpass))

    def save_preferences(self):
        settings = QSettings()
        url = self.web_url_input.text()
        secret = self.secret_input.text()

        if not url:
            QMessageBox.warning(self, "Erreur", "L'URL ne peut pas être vide")
            return
        if not secret:
            QMessageBox.warning(self, "Erreur", "Le mot de passe ne peut pas être vide")
            return
        
        settings.setValue("web_url", url)
        settings.setValue("unlockpass", secret)
        self.accept()

    def get_secret_sequence(self):
        return self.secret_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.load_preferences()
        #self.sse_client = SSEClient(self)
        #self.sse_client.sse_print.connect(self.print_ticket)
        #self.sse_client.start()
        self.start_socket_io_client(self.web_url)
        
    def start_socket_io_client(self, url):
        print(f"Starting Socket.IO client with URL: {url}")
        self.socket_io_client = WebSocketClient(url)
        self.socket_io_client.signal_print.connect(self.print_ticket)
        #self.socket_io_client.new_notification.connect(self.show_notification)
        #self.socket_io_client.my_patient.connect(self.update_my_patient)
        self.socket_io_client.start()              


        self.web_view = QWebEngineView()
        url = self.web_url + "/patient"
        self.web_view.setUrl(url)
        self.setCentralWidget(self.web_view)
        
        # Connecter le signal loadFinished pour injecter les balises <meta> (bloquer le pinch)
        self.web_view.loadFinished.connect(self.inject_meta_tags)

        # Fullscreen mode
        self.showFullScreen()

        # Set up shortcut to unlock configuration menu
        self.typed_sequence = ""
        
        # Create Preferences Dialog
        self.preferences_dialog = PreferencesDialog(self)
        self.preferences_dialog.load_preferences()
        
        # Create Menu
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        self.config_menu = QMenu("Menu", self)
        self.menu_bar.addMenu(self.config_menu)

        self.preferences_action = QAction("Préférences", self)
        self.preferences_action.triggered.connect(self.open_preferences)
        self.config_menu.addAction(self.preferences_action)

        self.fullscreen_action = QAction("Plein Écran", self)
        self.fullscreen_action.triggered.connect(self.enter_fullscreen)
        self.config_menu.addAction(self.fullscreen_action)
        
        self.menu_bar.hide()  # Hide the menu bar initially
        
    def inject_meta_tags(self):
        """ Permet de bloquer le pinch sur la page web, mais CTRL+Scrolling """
        js_code = """document.body.addEventListener('touchstart', function(e) {
            if ( (e.touches.length > 1) || e.targetTouches.length > 1) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            }
            }, {passive: false});
        """
        self.web_view.page().runJavaScript(js_code)

    def print_ticket(self, message):
        print("Message:", message)
        try:
            print_functions.print_ticket(message)
        except Exception as e:
            print(f"Erreur lors de l'impression: {e}")

    def load_preferences(self):
        settings = QSettings()
        self.web_url = settings.value("web_url", "http://localhost:5000")
        self.unlockpass = settings.value("unlockpass", default_unlockpass)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()  # Ignore the escape key to prevent exit from fullscreen
        
        # Capture keystrokes for unlocking configuration
        self.typed_sequence += event.text()
        if self.unlockpass in self.typed_sequence:
            self.typed_sequence = ""  # Reset sequence after successful match
            self.showNormal()  # Exit fullscreen mode to show menu bar
            self.menu_bar.show()
        
        super().keyPressEvent(event)
    
    def open_preferences(self):
        if self.preferences_dialog.exec() == QDialog.Accepted:
            new_secret = self.preferences_dialog.get_secret_sequence()
            if new_secret:
                self.unlockpass = new_secret
                settings = QSettings()
                settings.setValue("unlockpass", self.unlockpass)
                print(f"New secret sequence set: {self.unlockpass}")

    def enter_fullscreen(self):
        self.menu_bar.hide()
        self.showFullScreen()

if __name__ == "__main__":
    app = QApplication([])

    app.setApplicationName("PatientPage")
    app.setOrganizationName("PharmaFile")
    app.setOrganizationDomain("mycompany.com")

    window = MainWindow()
    window.show()
    app.exec()