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
    def __init__(self, idVendor, idProduct, printer_model):
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.printer_model = printer_model
        
        try:
            self.p = Usb(idVendor, idProduct, profile=printer_model)
        except USBNotFoundError:
            print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
            self.p = None
        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
            self.p = None
        
    def print(self, data):
        if self.p is None:
            print("Erreur : L'imprimante n'est pas initialisée correctement.")
            return False
        
        try:
            print("Émission du signal avec le message :", data)
            self.p.text(data)
            self.p.cut()
            return True
        except Exception as e:
            print(f"Erreur lors de l'impression : {e}")
            return False  