import threading
import requests
from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError

try:
    p = Usb(0x04b8, 0x0202, profile="TM-T88II")
except USBNotFoundError:
    print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
    p = None  # Définir p à None pour éviter d'autres erreurs


def print_ticket(data):
    print("Emitting signal with message:", data)
    p.text(data)
    p.cut()
    

class Printer(object):
    def __init__(self, idVendor, idProduct, printer_model, web_url):
        self.idVendor = int(idVendor, 16)
        self.idProduct = int(idProduct, 16)
        self.printer_model = printer_model
        self.web_url = web_url
        
        try:
            self.p = Usb(idVendor, idProduct, profile=printer_model)
        except USBNotFoundError:
            print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
            self.send_printer_error("Imprimante USB non trouvée.")
            self.p = None
        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
            self.send_printer_error(f"Erreur lors de l'initialisation : {e}")
            self.p = None
        
    def print(self, data):
        if self.p is None:
            print("Erreur : L'imprimante n'est pas initialisée correctement.")
            self.send_printer_error("Imprimante non initialisée correctement.")
            return False
        
        try:
            print("Émission du signal avec le message :", data)
            self.p.text(data)
            self.p.cut()
            return True
        except Exception as e:
            print(f"Erreur lors de l'impression : {e}")
            self.send_printer_error(f"Erreur lors de l'impression : {e}")
            return False

    def send_printer_error(self, error_message):
        def send_request():
            try:
                url = f"{self.web_url}/printer/error"
                payload = {'error': True, 'message': error_message}
                response = requests.post(url, json=payload)
                response.raise_for_status()
                print(f"Erreur signalée au serveur : {error_message}")
            except requests.exceptions.RequestException as e:
                print(f"Échec de l'envoi du message d'erreur au serveur : {e}")

        thread = threading.Thread(target=send_request)
        thread.start()