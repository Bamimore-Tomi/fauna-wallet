import os, json, base64, time
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from faunadb.errors import NotFound
from tronapi import Tron
from tronapi.common.account import PrivateKey
from dotenv import load_dotenv

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

import keyboards
import errors


def load_db():
    load_dotenv()
    client = FaunaClient(secret=os.getenv("FAUNA-KEY"))
    return client


def load_messages():
    f = open("messages.json", "r")
    messages = json.load(f)
    return messages


def wallet_name_validator(text: str) -> str:
    text = str(text).strip()
    if len(text) > 12 or len(text) < 1:
        return False, None
    return True, text.lower()


def _generate_fernet_key(master_key: str, salt: str) -> str:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt.encode(),
        iterations=100000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
    return key.decode("utf-8")


def _encrypt_private_key(private_key: str, fernet_key: str) -> str:
    encryptor = Fernet(fernet_key)
    hash = encryptor.encrypt(private_key.encode())
    return hash.decode()


def _decrypt_private_key(hash, key) -> str:
    decryptor = Fernet(key)
    private_key = decryptor.decrypt(hash.encode())
    return private_key.decode()


def save_user(client, data):
    user = client.query(
        q.create(
            q.collection("user"),
            {"data": data},
        )
    )


def get_wallets(client, user_id):
    wallets = client.query(q.paginate(q.match(q.index("wallet_index"), user_id)))
    if len(wallets["data"]) < 1:
        raise errors.WalletNotFound

    wallets_data = [
        q.get(q.ref(q.collection("wallet"), wallet.id())) for wallet in wallets["data"]
    ]
    wallets_data = client.query(wallets_data)
    return [i["data"] for i in wallets_data]


def generate_wallet_menu(client, user_id):
    data = get_wallets(client, user_id)
    menu = keyboards.wallet_menu(data)
    return menu


def create_wallet(client, user_id, wallet_name) -> bool:
    tron = Tron()
    account = tron.create_account
    address = account.address
    fernet_key = _generate_fernet_key(os.getenv("MASTER"), os.getenv("SALT"))
    encrypted_private_key = _encrypt_private_key(account.private_key, fernet_key)
    wallet = client.query(
        q.create(
            q.collection("wallet"),
            {
                "data": {
                    "user_id": user_id,
                    "wallet_name": wallet_name,
                    "encrypted_private_key": encrypted_private_key,
                    "public_key": account.public_key,
                    "wallet_address": dict(address),
                    "wallet_account_balance": 0.0,
                    "transactions": [],
                    "date_generated": time.time(),
                }
            },
        )
    )
    return address.base58


if __name__ == "__main__":
    client = load_db()
    print(generate_wallet_menu(client, 1766860738))
