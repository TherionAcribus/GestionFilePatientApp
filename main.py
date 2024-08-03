import json
import time
import sys
import os
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QVBoxLayout,
                                QLineEdit, QPushButton, QDialog, QFormLayout,
                                QMenuBar, QMessageBox, QCheckBox, QLabel)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtGui import QAction
from requests.exceptions import RequestException


from print_functions import Printer
from websocket_client import WebSocketClient


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
        
        form_layout = QFormLayout()
        
        self.use_password_checkbox = QCheckBox("Utiliser un mot de passe pour débloquer le plein écran", self)
        self.use_password_checkbox.stateChanged.connect(self.toggle_password_field)
        form_layout.addRow(self.use_password_checkbox)

        self.secret_input = QLineEdit(self)
        self.secret_label = QLabel("Mot pour débloquer le plein écran:")
        form_layout.addRow(self.secret_label, self.secret_input)

        self.web_url_input = QLineEdit(self)
        form_layout.addRow("URL de la page web:", self.web_url_input)
        
        self.username_input = QLineEdit(self)
        form_layout.addRow("Nom d'utilisateur:", self.username_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Mot de passe:", self.password_input)

        self.idVendor_input = QLineEdit(self)
        form_layout.addRow("Imprimante - idVendor:", self.idVendor_input)

        self.idProduct_input = QLineEdit(self)
        form_layout.addRow("Imprimante - idProduct:", self.idProduct_input)

        self.printer_model_input = QLineEdit(self)
        form_layout.addRow("Imprimante - Modèle:", self.printer_model_input)

        self.save_button = QPushButton("Enregistrer", self)
        self.save_button.clicked.connect(self.save_preferences)

        self.main_layout.addLayout(form_layout)
        self.main_layout.addWidget(self.save_button)

        self.setLayout(self.main_layout)
        
    def toggle_password_field(self, state):
        # 2 = Checked
        self.secret_input.setEnabled(state == 2)
        self.secret_label.setEnabled(state == 2)

    def load_preferences(self):
        """ chargement des préférences"""
        settings = QSettings()
        use_password = settings.value("use_password", False, type=bool)
        self.use_password_checkbox.setChecked(use_password)
        self.secret_input.setText(settings.value("unlockpass", ""))
        self.secret_input.setEnabled(use_password)
        self.secret_label.setEnabled(use_password)
        self.web_url_input.setText(settings.value("web_url", "http://localhost:5000"))
        self.username_input.setText(settings.value("username", "admin"))
        self.password_input.setText(settings.value("password", "admin"))
        self.idVendor_input.setText(settings.value("idVendor", ""))
        self.idProduct_input.setText(settings.value("idProduct", ""))
        self.printer_model_input.setText(settings.value("printer", ""))


    def save_preferences(self):
        """ sauvegarde des préférences"""
        settings = QSettings()
        url = self.web_url_input.text()
        use_password = self.use_password_checkbox.isChecked()
        secret = self.secret_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        idVendor = self.idVendor_input.text()
        idProduct = self.idProduct_input.text()
        printer = self.printer_model_input.text()
        
        if not url:
            QMessageBox.warning(self, "Erreur", "L'URL ne peut pas être vide")
            return
        if not secret:
            QMessageBox.warning(self, "Erreur", "Le mot de passe ne peut pas être vide")
            return
        
        settings.setValue("web_url", url)        
        settings.setValue("username", username)
        settings.setValue("password", password)
        settings.setValue("use_password", use_password)
        settings.setValue("unlockpass", secret)
        settings.setValue("idVendor", idVendor)
        settings.setValue("idProduct", idProduct)
        settings.setValue("printer", printer)

        self.accept()
        
        # rechargement des préférences pour être appliquées immédiatement
        self.parent().load_preferences()

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

        self.printer = Printer(self.idVendor, self.idProduct, self.printer_model)

        self.web_view = QWebEngineView()
        url = self.web_url + "/patient"
        self.web_view.setUrl(url)
        self.setCentralWidget(self.web_view)
        
        # Connect to the URL changed signal. On recherche la page login pour la remplir
        self.web_view.urlChanged.connect(self.on_url_changed)

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

        self.fullscreen_action = QAction("Plein Écran (F11)", self)
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
        
    def start_socket_io_client(self, url):
        """ démarrage de socket.io client """
        print(f"Starting Socket.IO client with URL: {url}")
        self.socket_io_client = WebSocketClient(url)
        self.socket_io_client.signal_print.connect(self.print_ticket)
        #self.socket_io_client.new_notification.connect(self.show_notification)
        #self.socket_io_client.my_patient.connect(self.update_my_patient)
        self.socket_io_client.start()    

    def print_ticket(self, message):
        """ Impression du ticket """
        print("Message:", message)
        try:
            self.printer(message)
        except Exception as e:
            print(f"Erreur lors de l'impression: {e}")
            
    def on_url_changed(self, url):
        # Check if 'login' appears in the URL
        print("URL changed:", url.toString())
        if "login" in url.toString():
            self.inject_login_script()            

    def inject_login_script(self):
        print("Injection de code JS")
        print(self.username, self.password)
        # Inject JavaScript to fill and submit the login form automatically
        script = f"""
        document.addEventListener('DOMContentLoaded', function() {{
        console.log("Injecting login script after DOM is fully loaded");
        var usernameInput = document.querySelector('input[name="username"]');
        var passwordInput = document.querySelector('input[name="password"]');
        var rememberCheckbox = document.querySelector('input[name="remember"]');
        
        if (usernameInput) {{
            console.log("Found username input");
            usernameInput.value = "{self.username}";
        }} else {{
            console.log("Username input not found");
        }}

        if (passwordInput) {{
            console.log("Found password input");
            passwordInput.value = "{self.password}";
        }} else {{
            console.log("Password input not found");
        }}

        if (rememberCheckbox) {{
            console.log("Found remember me checkbox");
            rememberCheckbox.checked = true;
        }} else {{
            console.log("Remember me checkbox not found");
        }}

        var form = usernameInput ? usernameInput.closest('form') : null;
        if (form) {{
            console.log("Found form, submitting");
            form.submit();
        }} else {{
            console.log("Form not found");
        }}
    }});
    """
        self.web_view.page().runJavaScript(script)


    def load_preferences(self):
        """ Chargement des préférences"""
        settings = QSettings()
        self.web_url = settings.value("web_url", "http://localhost:5000")
        self.use_password = settings.value("use_password", False, type=bool)
        self.unlockpass = settings.value("unlockpass", "")
        self.username = settings.value("username", "admin")
        self.password = settings.value("password", "admin")
        self.idVendor = settings.value("idVendor", "")
        self.idProduct = settings.value("idProduct", "")
        self.printer_model = settings.value("printer", "")

    def keyPressEvent(self, event):
        """ capture des touches du clavier pour réduire l'App """
        if event.key() == Qt.Key_Escape:
            event.ignore()  # Ignore la touche Escape pour empêcher la sortie du plein écran

        if self.use_password:
            # Full screen avec F11 (mais pas pour réduire)
            if event.key() == Qt.Key_F11:
                if self.isFullScreen():
                    QMessageBox.information(self, "Mode plein écran", 
                                            "La saisie du mot de passe est obligatoire pour quitter le mode plein écran.")
                else:
                    self.showFullScreen()
                    self.menu_bar.hide() 
                
            # Capture des frappes pour déverrouiller la configuration si use_password est True
            self.typed_sequence += event.text()
            if self.unlockpass in self.typed_sequence:
                self.typed_sequence = ""  # Réinitialise la séquence après une correspondance réussie
                self.showNormal()  # Quitte le mode plein écran pour afficher la barre de menu
                self.menu_bar.show()
        else:
            # Utilise F11 pour basculer entre le mode plein écran et normal si use_password est False
            if event.key() == Qt.Key_F11:
                if self.isFullScreen():
                    self.showNormal()
                    self.menu_bar.show()
                else:
                    self.showFullScreen()
                    self.menu_bar.hide()
        
        super().keyPressEvent(event)
    
    def open_preferences(self):
        """ Ouvre la page des préférences """
        if self.preferences_dialog.exec() == QDialog.Accepted:
            new_secret = self.preferences_dialog.get_secret_sequence()
            if new_secret:
                self.unlockpass = new_secret
                settings = QSettings()
                settings.setValue("unlockpass", self.unlockpass)
                print(f"New secret sequence set: {self.unlockpass}")

    def enter_fullscreen(self):
        """ Retourner en plein écran"""
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