from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError
from request_handler import RequestThread

try:
    p = Usb(0x04b8, 0x0202, profile="TM-T88II")
except USBNotFoundError:
    print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
    p = None  # Définir p à None pour éviter d'autres erreurs


def print_ticket(data):
    print("Emitting signal with message:", data)
    p.text(data)
    p.cut()
    

class Printer:
    def __init__(self, idVendor, idProduct, printer_model, web_url, session, app_token):
        self.idVendor = int(idVendor, 16)
        self.idProduct = int(idProduct, 16)
        self.printer_model = printer_model
        self.session = session
        self.web_url = web_url
        self.app_token = app_token
        self.p = None
        self.initialize_printer()
    
    def initialize_printer(self):
        try:
            self.p = Usb(self.idVendor, self.idProduct, profile=self.printer_model)
            self.send_printer_status(False, "Imprimante USB initialisée avec succès.")
            print("Imprimante initialisée avec succès.")
        except USBNotFoundError:
            print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
            self.p = None
            self.send_printer_status(True, "Imprimante USB non trouvée.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
            self.p = None
            self.send_printer_status(True, f"Erreur lors de l'initialisation : {e}")

    def print(self, data):
        if self.p is None:
            print("Erreur : L'imprimante n'est pas initialisée correctement.")
            self.send_printer_status(True, "Imprimante non initialisée correctement.")
            return False

        try:
            print("Émission du signal avec le message :", data)
            self.p.text(data)
            self.p.cut()
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