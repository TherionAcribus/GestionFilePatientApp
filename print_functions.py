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
        
        idVendor = idVendor
        idProduct = idProduct
        printer_model = printer_model
        
        try:
            p = Usb(idVendor, idProduct, profile=printer_model)
        except USBNotFoundError:
            print("Avertissement : Imprimante USB non trouvée. Assurez-vous que l'imprimante est connectée.")
            p = None  # Définir p à None pour éviter d'autres erreurs
        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
        
    def print(self, data):
        p.text(data)
        p.cut()    