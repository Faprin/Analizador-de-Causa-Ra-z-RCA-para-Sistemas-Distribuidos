import time
import requests
import random
import threading

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

    # response.raise_for_status()
    return response.json().get("token")


# ========================
#   PETICIONES A SERVIDOR
# ========================
def request_normal(headers):
    calls = [
        lambda: requests.get(f"{url_inventario}/inventario", headers=headers),
        lambda: requests.get(f"{url_inventario}/inventario/1", headers=headers),
        lambda: requests.get(f"{url_pedidos}/pedidos", headers=headers),
    ]

    fn = random.choice(calls)
    response = fn()
    print(f"[NORMAL] {response.request.method} {response.url} {response.status_code}")


def request_error_inventario(headers):
    calls = [
        lambda: requests.post(
            f"{url_inventario}/chaos/db-saturate",
            headers = headers,
            params={"segundos": 6}
        ),

        lambda: requests.post(
            f"{url_inventario}/chaos/error",
            headers = headers,
            params={"type": "npe"}
        ),

        lambda: requests.post(
            f"{url_inventario}/chaos/error",
            headers = headers,
            params={"type": "db"} # RuntimeError
        )
    ]

    fn = random.choice(calls)
    try:
        response = fn()
        print(f"[CHAOS] {response.request.method} {response.url} {response.status_code}")

    except requests.exceptions.Timeout:
        print(f"[CHAOS]   Timeout esperado al inyectar caos")
    except requests.exceptions.ConnectionError as e:
        print(f"[CHAOS]   ConnectionError: {e}")
    except Exception as e:
        print(f"[CHAOS]   Error: {e}")

def request_error_pedidos(headers):
    calls = [
        lambda: requests.post(
            f"{url_pedidos}/chaos/db-saturate",
            headers = headers,
            params={"segundos": 6}
        ),

        lambda: requests.post(
            f"{url_pedidos}/chaos/error",
            headers = headers,
            params={"type": "npe"}
        ),

        lambda: requests.post(
            f"{url_pedidos}/chaos/error",
            headers = headers,
            params={"type": "db"} # RuntimeError
        )
    ]

    fn = random.choice(calls)
    try:
        response = fn()
        print(f"[CHAOS] {response.request.method} {response.url} {response.status_code}")

    except requests.exceptions.Timeout:
        print(f"[CHAOS]   Timeout esperado al inyectar caos")
    except requests.exceptions.ConnectionError as e:
        print(f"[CHAOS]   ConnectionError: {e}")
    except Exception as e:
        print(f"[CHAOS]   Error: {e}")


def request_cascade_error(headers):

    # dejamos al servidor sin conexion 15 segundos la basse de datos desde un hilo diferente
    def saturar():
        try:
            requests.post(
                f"{url_inventario}/chaos/db-saturate",
                headers=headers,
                params={"segundos": 8},
                timeout=12
            )
        except Exception:
            pass  # el timeout del hilo es esperado, no nos importa

    threading.Thread(target=saturar).start()

    time.sleep(1)

    print("[CASCADE] Creando pedido mientras inventario está saturado...")

    try:
        request = requests.post(
            f"{url_pedidos}/pedidos",
            headers = headers,
            json = {
                "clienteId": 1,
                "productoId": 1,
                "cantidad": 1,
                "precioUnitario": 20
            },
            timeout=6
        )
    
        if request.status_code == 500:
            print(f"[CASCADE] Fallo en cascada confirmado {request.status_code}")
        else:
            print(f"[CASCADE] Pedido {request.status_code}")

    except requests.exceptions.Timeout:
        print("[CASCADE] Timeout de red en pedidos")
    except Exception as e:
        print(f"[CASCADE] Error: {e}")


# ========================
#   MAIN
# ========================
if __name__ == "__main__":
    print("[ ] GENERANDO DATASET")

    token = getToken()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json"
    }

    iteration = 0

    while iteration < 1000:    
        roll = random.random()
        iteration += 1

        if roll < 0.6:
            request_normal(headers=headers)
        elif roll < 0.8: 
            # request_error_inventario(headers=headers)
            request_error_pedidos(headers=headers)
        else:
            request_cascade_error(headers=headers)

        time.sleep(random.uniform(0.2, 1.0)) # tiempo entre peticiones

        if iteration % 100 == 0: 
            print("\n[AUTH] Renovando token...")
            token = getToken()
            headers["Authorization"] = f"Bearer {token}"

