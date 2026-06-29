import requests
import random

from urllib3 import request

# URL´s de los microservicios
url_pedidos = "http://localhost:8081" # pedidos
url_inventario = "http://localhost:8080" # inventario
url_autenticacion = "http://localhost:8082" # autenticacion

def getToken():
    response = requests.post(
        f"{url_autenticacion}/api/auth/login",
        json = {
            "username" : "Faprin", 
            "password": "1234",
            }
    )

    return response.json().get("token")


def request_normal():
    calls = [
        lambda: requests.get(f"{url_inventario}/inventario", headers=headers),
        lambda: requests.get(f"{url_inventario}/inventario/1", headers=headers),
        lambda: requests.get(f"{url_pedidos}/pedidos", headers=headers),
    ]
