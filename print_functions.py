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
            with self.token_lock:
                token = self.app_token

            if token is None:
                print("Pas de token disponible, impossible d'envoyer l'erreur au serveur.")
                return

            try:
                url = f"{self.web_url}/printer/error"
                payload = {'error': error_message}
                headers = {'Authorization': f'Bearer {token}'}  # Ou incluez le token selon vos besoins
                response = self.session.post(url, json=payload, headers=headers)
                if response.status_code == 401:
                    # Token expiré ou invalide, essayez de le renouveler
                    print("Token expiré ou invalide, tentative de renouvellement...")
                    self.get_app_token()
                    with self.token_lock:
                        token = self.app_token
                    if token:
                        headers['Authorization'] = f'Bearer {token}'
                        response = self.session.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        print(f"Erreur signalée au serveur après renouvellement du token : {error_message}")
                    else:
                        print("Impossible de renouveler le token.")
                else:
                    response.raise_for_status()
                    print(f"Erreur signalée au serveur : {error_message}")
            except requests.exceptions.RequestException as e:
                print(f"Échec de l'envoi du message d'erreur au serveur : {e}")

        thread = threading.Thread(target=send_request)
        thread.start()


    def get_app_token(self):
        url = f'{self.web_url}/api/get_app_token'
        data = {'app_secret': 'votre_secret_app'}
        response = self.session.post(url, data=data)
        if response.status_code == 200:
            self.app_token = response.json()['token']
            print("Token obtenu :", self.app_token)
        else:
            print("Échec de l'obtention du token")