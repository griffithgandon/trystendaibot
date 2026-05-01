import requests
import json
import time
from uuid import uuid4
from config import PANEL_URL, USERNAME, PASSWORD, INBOUND_IDS, SUB_BASE_URL, DOMAIN, PORT

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()


# ===== LOGIN =====
def login():
    session.post(
        f"{PANEL_URL}/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        },
        verify=False
    )


# ===== CREATE USER =====
def create_user(user_id, days):
    login()

    expire = int((time.time() + days * 86400) * 1000)

    for inbound_id in INBOUND_IDS:
        client_id = str(uuid4())

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": client_id,
                    "email": str(user_id),  # 🔥 одинаковый email
                    "limitIp": 1,
                    "totalGB": 0,
                    "expiryTime": expire
                }]
            })
        }

        r = session.post(
            f"{PANEL_URL}/panel/api/inbounds/addClient",
            json=payload,
            verify=False
        )

        print(f"ADD → {inbound_id}:", r.status_code)

    return True


# ===== DELETE USER =====
def delete_user(user_id):
    login()

    r = session.get(
        f"{PANEL_URL}/panel/api/inbounds/list",
        verify=False
    )

    data = r.json()
    success = False

    for inbound in data.get("obj", []):
        inbound_id = inbound.get("id")

        for client in inbound.get("clientStats", []):
            if client.get("email") == str(user_id):

                uuid = client.get("uuid")

                r = session.post(
                    f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{uuid}",
                    verify=False
                )

                print(f"DELETE → {inbound_id}:", r.status_code)

                try:
                    if r.json().get("success"):
                        success = True
                except:
                    pass

    return success


# ===== GET VPN DATA =====
def get_vpn_data(user_id):
    login()

    r = session.get(
        f"{PANEL_URL}/panel/api/inbounds/list",
        verify=False
    )

    data = r.json()

    uuid = None
    sub_id = None

    for inbound in data.get("obj", []):
        for client in inbound.get("clientStats", []):

            if client.get("email") == str(user_id):

                if not uuid:
                    uuid = client.get("uuid")

                if not sub_id:
                    sub_id = client.get("subId")

    if not uuid:
        return None

    # 👉 VLESS
    vless = f"vless://{uuid}@{DOMAIN}:{PORT}?type=xhttp&security=reality"

    # 👉 SUBSCRIPTION
    sub = None
    if sub_id:
        sub = f"{SUB_BASE_URL}{sub_id}"

    return {
        "vless": vless,
        "subscription": sub
    }