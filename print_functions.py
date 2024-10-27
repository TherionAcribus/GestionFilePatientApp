import re
import base64
from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError
from request_handler import RequestThread
from PySide6.QtCore import QObject, Slot

try:
    p = Usb(0x04b8, 0x0202, profile="TM-T88II")
except USBNotFoundError:
    print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
    p = None  # Définir p à None pour éviter d'autres erreurs

def print_ticket(data):
    print("Emitting signal with message:", data)
    p.text(data)
    p.cut()

class Bridge(QObject):
    def __init__(self, printer):
        super().__init__()
        self.printer = printer

    @Slot(str)
    def print_ticket(self, message):
        print(f"Received message to print: {message}")

        if self.printer:
            self.printer.print(message)
        else:
            print("Printer not available")

class Printer:
    def __init__(self, idVendor, idProduct, printer_model, web_url, session, app_token):
        self.idVendor = int(idVendor, 16)
        self.idProduct = int(idProduct, 16)
        self.printer_model = printer_model
        self.session = session
        self.web_url = web_url
        self.app_token = app_token
        self.p = None
        self.error = None
        self.encoding = 'utf-8'
        self.initialize_printer()
    
    def initialize_printer(self):
        try:
            self.p = Usb(self.idVendor, self.idProduct, profile=self.printer_model)
            self.send_printer_status(False, "Imprimante USB initialisée avec succès.")
            self.error = False
            print("Imprimante initialisée avec succès.")
        except USBNotFoundError:
            print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
            self.p = None
            self.error = True
            self.send_printer_status(True, "Imprimante USB non trouvée.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
            self.p = None
            self.error = True
            self.send_printer_status(True, f"Erreur lors de l'initialisation : {e}")

    def print(self, data):
        if self.p is None:
            print("Erreur : L'imprimante n'est pas initialisée correctement.")
            self.error = True
            self.send_printer_status(True, "Imprimante non initialisée correctement.")
            return False

        try:
            data = base64.b64decode(data).decode(self.encoding)
            print("Émission du signal avec le message :", data)
            self.p.text(data)
            self.p.cut()
            if self.error:
                self.error = False
                self.send_printer_status(False, "Impression réussie.")
            return True
        except Exception as e:
            print(f"Erreur lors de l'impression : {e}")
            self.send_printer_status(True, f"Erreur lors de l'impression : {e}")
            return False
        
    def send_printer_status(self, error, error_message):
        url = f'{self.web_url}/api/printer/status'
        data = {'error': error, 'message': error_message}
        headers = {
            'X-App-Token': self.app_token,
            'Content-Type': 'application/json'  # Ajoutez l'en-tête Content-Type pour le JSON
        }
        
        # Envoyer les données au format JSON
        self.printer_thread = RequestThread(url, self.session, method='POST', json=data, headers=headers)
        #self.printer_thread.result.connect(self.handle_user_result)
        self.printer_thread.start()
        


