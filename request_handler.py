from requests.exceptions import RequestException
from PySide6.QtCore import Signal, QThread

class RequestThread(QThread):
    result = Signal(str, str, int)  # Correction du type de signal si nécessaire

    def __init__(self, url, session, method='GET', data=None, json=None, headers=None):
        super().__init__()
        self.url = url
        self.session = session
        self.method = method
        self.data = data
        self.json = json  # Ajout du paramètre json
        self.headers = headers

    def run(self):
        print("Requesting URL:", self.url)
        try:
            if self.method == 'GET':
                response = self.session.get(self.url, headers=self.headers)
            elif self.method == 'POST':
                if self.json:  # Si json est spécifié, l'utiliser pour l'envoi
                    response = self.session.post(self.url, json=self.json, headers=self.headers)
                else:
                    response = self.session.post(self.url, data=self.data, headers=self.headers)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {self.method}")
            
            self.result.emit("", response.text, response.status_code)
        except RequestException as e:
            self.result.emit(str(e), "", 0)
