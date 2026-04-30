import requests
import json
import time
from uuid import uuid4
from config import *

session = requests.Session()


def login():
    session.post(
        f"{PANEL_URL}/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        }
    )


def create_or_update_user(user_id, days, existing=None):

    login()

    client_id = existing if existing else uuid4().hex

    expire = int((time.time() + days * 86400) * 1000)

    payload = {
        "id": INBOUND_ID,
        "settings": json.dumps({
            "clients": [{
                "id": client_id,
                "email": str(user_id),
                "limitIp": 1,
                "totalGB": 0,
                "expiryTime": expire
            }]
        })
    }

    endpoint = "updateClient" if existing else "addClient"

    r = session.post(
        f"{PANEL_URL}/panel/api/inbounds/{endpoint}",
        json=payload
    )

    if r.status_code == 200:
        return client_id

    return None