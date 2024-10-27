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
        

def word_wrap(text, line_width):
    """
    Enveloppe le texte à la largeur de ligne spécifiée, sans couper les mots.
    """
    lines = []
    paragraphs = text.split('\n')  # Diviser le texte en paragraphes

    for paragraph in paragraphs:
        words = paragraph.split(' ')
        current_line = ''
        for word in words:
            # Vérifier si le mot dépasse la largeur de ligne
            if len(current_line + ' ' + word) > line_width:
                lines.append(current_line)
                current_line = word
            else:
                if current_line:
                    current_line += ' ' + word
                else:
                    current_line = word
        if current_line:
            lines.append(current_line)
    return '\n'.join(lines)


def convert_markdown_to_escpos(markdown_text, line_width=42):
    # Commandes ESC/POS
    escpos_commands = {
        'center_on': '\x1b\x61\x01',
        'center_off': '\x1b\x61\x00',
        'double_size_on': '\x1d\x21\x11',
        'double_size_off': '\x1d\x21\x00',
        'bold_on': '\x1b\x45\x01',
        'bold_off': '\x1b\x45\x00',
        'underline_on': '\x1b\x2d\x01',
        'underline_off': '\x1b\x2d\x00',
        'separator': '-' * line_width + '\n',
    }

    # Motifs Markdown
    patterns = {
        'center': re.compile(r'\[center\](.*?)\[\/center\]', re.DOTALL),
        'double_size': re.compile(r'\[double\](.*?)\[\/double\]', re.DOTALL),
        'bold': re.compile(r'\*\*(.*?)\*\*', re.DOTALL),
        'underline': re.compile(r'__(.*?)__', re.DOTALL),
        'separator': re.compile(r'\[separator\]', re.DOTALL),
    }

    def replace_pattern(pattern, on_command, off_command, text, adjust_width=True):
        def wrap_and_format(match):
            inner_text = match.group(1)
            # Ajuster la largeur si en double taille
            width = line_width // 2 if adjust_width else line_width
            wrapped_text = word_wrap(inner_text, width)
            return f"{on_command}{wrapped_text}{off_command}"
        return pattern.sub(wrap_and_format, text)

    # Gérer les sauts de ligne explicitement
    escpos_text = markdown_text.replace('\\n', '\n')

    # Appliquer les transformations basées sur les motifs Markdown
    escpos_text = replace_pattern(patterns['center'], escpos_commands['center_on'], escpos_commands['center_off'], escpos_text, adjust_width=False)
    escpos_text = replace_pattern(patterns['double_size'], escpos_commands['double_size_on'], escpos_commands['double_size_off'], escpos_text)
    escpos_text = replace_pattern(patterns['bold'], escpos_commands['bold_on'], escpos_commands['bold_off'], escpos_text, adjust_width=False)
    escpos_text = replace_pattern(patterns['underline'], escpos_commands['underline_on'], escpos_commands['underline_off'], escpos_text, adjust_width=False)
    escpos_text = patterns['separator'].sub(escpos_commands['separator'], escpos_text)

    # Appliquer le retour à la ligne au texte brut restant
    # Nous devons faire attention à ne pas altérer les commandes ESC/POS insérées
    # Nous pouvons diviser le texte en parties, en conservant les commandes ESC/POS intactes

    # Expression régulière pour séparer le texte en gardant les commandes ESC/POS
    split_pattern = re.compile('(\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x1b]*\x1b\\\\|\x1b.|[\x00-\x1F])')

    parts = split_pattern.split(escpos_text)
    wrapped_parts = []

    for part in parts:
        # Si la partie est une commande ESC/POS, on la laisse telle quelle
        if re.match(split_pattern, part):
            wrapped_parts.append(part)
        else:
            # Appliquer le retour à la ligne
            wrapped_text = word_wrap(part, line_width)
            wrapped_parts.append(wrapped_text)

    escpos_text = ''.join(wrapped_parts)

    return escpos_text