import os
os.environ["QT_QPA_PLATFORM"] = "xcb"  # forcage de l'utilisation de X11 au lieu de Wayland. Wayland peut provoquer des gels de l'App si instabilité de la connexion avec l'écran.
import sys
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QVBoxLayout,
                                QLineEdit, QPushButton, QDialog, QFormLayout,
                                QMenuBar, QMessageBox, QCheckBox, QLabel)
from PySide6.QtWebEngineWidgets import QWebEngineView 
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import Qt, QSettings, Signal, QTimer, QEvent
from PySide6.QtGui import QAction
from PySide6.QtWebChannel import QWebChannel
from datetime import datetime
import logging

from print_functions import Printer, Bridge
from websocket_client import WebSocketClient


def resource_path(relative_path):
    """ Obtenez le chemin d'accès absolu aux ressources pour le mode PyInstaller. """
    try:
        # PyInstaller crée un dossier temporaire et y stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Configuration des logs
        logging.basicConfig(
            filename='touch_events.log',
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Afficher le message de la console JavaScript dans la console Python
        print(f"JS Console ({level}): {message} (Source: {sourceID}, Line: {lineNumber})")
    
    def acceptNavigationRequest(self, url, type, isMainFrame):
        # Empêcher la navigation par clic droit -> "Ouvrir dans un nouvel onglet"
        return super().acceptNavigationRequest(url, type, isMainFrame)
    
    def createWindow(self, windowType):
        # Empêcher l'ouverture de nouvelles fenêtres
        return None
        

class CustomWebEngineView(QWebEngineView):
    touch_event_detected = Signal()
    touch_test_failed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        
        self.last_touch_time = datetime.now()
        self.consecutive_no_touch = 0
        self.touch_check_interval = 60
        
        self.touch_timer = QTimer(self)
        self.touch_timer.timeout.connect(self.check_touch_status)
        self.touch_timer.start(self.touch_check_interval * 1000)
        
        self.touch_count = 0
        self.last_touch_positions = []
    
    def contextMenuEvent(self, event):
        event.ignore()
    
    def event(self, event):
        if event.type() in [QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd]:
            self.handle_touch_event(event)
        return super().event(event)
    
    def handle_touch_event(self, event):
        self.last_touch_time = datetime.now()
        self.touch_event_detected.emit()
        self.consecutive_no_touch = 0
        self.touch_count += 1
        
        if event.type() == QEvent.TouchBegin and hasattr(event, 'touchPoints'):
            pos = event.touchPoints()[0].pos()
            self.last_touch_positions.append((pos.x(), pos.y()))
            if len(self.last_touch_positions) > 10:
                self.last_touch_positions.pop(0)
        
        logging.info(f"Événement tactile détecté - Type: {event.type()} - Count: {self.touch_count}")
    
    def check_touch_status(self):
        time_since_last_touch = (datetime.now() - self.last_touch_time).total_seconds()
        
        if time_since_last_touch > self.touch_check_interval:
            self.consecutive_no_touch += 1
            logging.warning(f"Pas d'événement tactile depuis {time_since_last_touch:.1f} secondes")
            
            if self.consecutive_no_touch >= 3:
                self.run_touch_diagnostic()
        else:
            self.consecutive_no_touch = 0
    
    def run_touch_diagnostic(self):
        """Exécuter un diagnostic du système tactile"""
        logging.warning("Démarrage du diagnostic tactile")
        
        js_diagnostic = """
        (function checkTouchSupport() {
            let diagnosticResult = {
                touchPoints: navigator.maxTouchPoints,
                touchEnabled: 'ontouchstart' in window,
                pointerEnabled: Boolean(window.PointerEvent),
                lastTouchEvent: window.lastTouchEventTime || 'None'
            };
            
            try {
                let testTouch = new TouchEvent('touchstart', {
                    bubbles: true,
                    touches: [{
                        identifier: 0,
                        target: document.body,
                        clientX: 0,
                        clientY: 0
                    }]
                });
                diagnosticResult.canCreateEvents = true;
            } catch(e) {
                diagnosticResult.canCreateEvents = false;
                diagnosticResult.error = e.message;
            }
            
            return JSON.stringify(diagnosticResult);
        })();
        """
        
        def callback(result):
            try:
                if isinstance(result, str):
                    import json
                    result = json.loads(result)
                
                logging.info(f"Résultat diagnostic : {result}")
                if not result.get('touchEnabled', False) or not result.get('canCreateEvents', False):
                    self.touch_test_failed.emit()
                    logging.error("Diagnostic tactile échoué - Émission signal d'échec")
            except Exception as e:
                logging.error(f"Erreur lors du traitement du diagnostic : {e}")
        
        # Utilisation correcte de runJavaScript avec PySide6
        self.page().runJavaScript(js_diagnostic, 0, callback)

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

        # Ajout du switch pour activer/désactiver le WebSocket
        self.websocket_checkbox = QCheckBox("Activer le WebSocket", self)
        form_layout.addRow(self.websocket_checkbox)

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
        websocket_enabled = settings.value("websocket_enabled", True, type=bool)
        self.websocket_checkbox.setChecked(websocket_enabled)        


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
        websocket_enabled = self.websocket_checkbox.isChecked()

        if not url:
            QMessageBox.warning(self, "Erreur", "L'URL ne peut pas être vide")
            return
        if not secret and use_password:
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
        settings.setValue("websocket_enabled", websocket_enabled)

        self.accept()
        
        # rechargement des préférences pour être appliquées immédiatement
        self.parent().load_preferences()
        # Redémarrage de la connexion WebSocket en fonction de la nouvelle préférence
        self.parent().update_socket_io_connection()

    def get_secret_sequence(self):
        return self.secret_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.load_preferences()

        # Mettre à jour la connexion WebSocket
        self.update_socket_io_connection()

        self.app_token = None
        try:
            self.get_app_token()
            # si on a un token, on se considère comme connecté
            self.connected = True
            #self.loading_screen.update_last_line(" - OK ! Token obtenu")
        except Exception as e:
            print("Erreur lors de l'obtention du token :", e)
            self.connected = False
            #self.loading_screen.update_last_line(f"- Erreur : {e}")

        self.session = requests.Session()  # Session HTTP persistante
        
        self.printer = Printer(self.idVendor, self.idProduct, self.printer_model, self.web_url,self.session, self.app_token)
        # Créez le bridge et passez l'objet imprimante
        self.bridge = Bridge(self.printer)

        self.bridge.reload_requested.connect(self.web_view.perform_complete_reload)

        self.web_view = CustomWebEngineView()
        self.page = CustomWebEnginePage()
        self.web_view.setPage(self.page)

        # Configurez le WebChannel
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)        

        self.web_view.page().setWebChannel(self.channel)

        url = self.web_url + "/patient"
        self.web_view.setUrl(url)
        self.setCentralWidget(self.web_view)        

        # Connect to the URL changed signal. On recherche la page login pour la remplir
        self.web_view.urlChanged.connect(self.on_url_changed)

        # Connecter le signal loadFinished pour injecter les balises <meta> (bloquer le pinch)
        self.web_view.loadFinished.connect(self.inject_meta_tags)

        # Injection du JavaScript après chargement pour permettre rechargement du navigateur à chaque patient
        self.web_view.loadFinished.connect(self.inject_refresh_code)

        # Connecter le signal d'échec tactile
        self.web_view.touch_test_failed.connect(self.handle_touch_failure)

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


    def inject_refresh_code(self, ok):
            if ok:
                js_code = """
                // Modifier la fonction goToCancelPatient existante
                const originalGoToCancelPatient = window.goToCancelPatient;
                window.goToCancelPatient = function() {
                    // Demander un reload complet via le bridge
                    if (typeof bridge !== 'undefined') {
                        bridge.request_reload();
                    }
                    originalGoToCancelPatient();
                };
                
                // Modifier le comportement du bouton cancel
                const cancelBtn = document.getElementById('cancel_btn');
                if (cancelBtn) {
                    const originalClick = cancelBtn.onclick;
                    cancelBtn.onclick = function(e) {
                        // Demander un reload complet via le bridge
                        if (typeof bridge !== 'undefined') {
                            bridge.request_reload();
                        }
                        if (originalClick) {
                            originalClick.call(this, e);
                        }
                    };
                }
                
                // Surveiller les changements du timer
                const timerGauge = document.getElementById('timer_gauge');
                if (timerGauge) {
                    const observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                            if (mutation.type === 'attributes' && 
                                mutation.attributeName === 'style' &&
                                timerGauge.style.width === '0%') {
                                if (typeof bridge !== 'undefined') {
                                    bridge.request_reload();
                                }
                            }
                        });
                    });
                    
                    observer.observe(timerGauge, {
                        attributes: true
                    });
                }
                """
                self.web_view.page().runJavaScript(js_code, 0)
        
            
    def handle_console_message(self, level, message, line_number, source_id):
            print(f"JavaScript console ({level}): {message} (line {line_number}, source {source_id})")


    def get_app_token(self):
        url = f'{self.web_url}/api/get_app_token'
        data = {'app_secret': 'votre_secret_app'}
        response = self.session.post(url, data=data)
        if response.status_code == 200:
            self.app_token = response.json()['token']
            print("Token obtenu :", self.app_token)
        else:
            print("Échec de l'obtention du token")
        
    def start_socket_io_client(self, url):
        """Démarrage de socket.io client"""
        print(f"Starting Socket.IO client with URL: {url}")
        self.socket_io_client = WebSocketClient(url)
        self.socket_io_client.signal_print.connect(self.print_ticket)
        self.socket_io_client.start()

    def stop_socket_io_client(self):
        """Arrêt de socket.io client"""
        if hasattr(self, 'socket_io_client'):
            print("Arrêt du client Socket.IO")
            self.socket_io_client.stop()
            # La méthode stop s'occupe maintenant de tout le nettoyage nécessaire
            print("Client Socket.IO arrêté avec succès")

    def update_socket_io_connection(self):
        """Démarre ou arrête le client SocketIO en fonction des préférences."""
        if self.websocket_enabled:
            self.start_socket_io_client(self.web_url)
        else:
            self.stop_socket_io_client()  

    def print_ticket(self, message):
        """ Impression du ticket """
        if self.printer.print(message):
            print("Ticket imprimé avec succès.")
        else:
            print("Échec de l'impression du ticket.")
                
            
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
        self.websocket_enabled = settings.value("websocket_enabled", True, type=bool)


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

    def handle_touch_failure(self):
        # Gérer l'échec du test tactile
        print("Problème tactile détecté!")
        # Ajouter votre logique de gestion ici


if __name__ == "__main__":
    app = QApplication([])

    app.setApplicationName("PatientPage")
    app.setOrganizationName("PharmaFile")
    app.setOrganizationDomain("mycompany.com")

    window = MainWindow()
    window.show()
    app.exec()