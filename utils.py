import os, json
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from tronapi import Tron
from tronapi.common.account import PrivateKey
from dotenv import load_dotenv

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet


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
    if len(text) > 12:
        return False, None
    if text.split(" ") > 1:
        return False, None
    return text


def _generate_fernet_key(self, master_key: str, salt: str) -> str:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt.encode(),
        iterations=100000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
    return key.decode("utf-8")


def _encrypt_private_key(self, private_key: str, fernet_key: str) -> str:
    encryptor = Fernet(fernet_key)
    hash = encryptor.encrypt(private_key.encode())
    return hash.decode()


def _decrypt_private_key(self, hash, key) -> str:
    decryptor = Fernet(key)
    private_key = decryptor.decrypt(hash.encode())
    return private_key.decode()


def create_wallet(user_id, wallet_name) -> bool:
    tron = Tron()
    account = tron.create_account
    address = account.address.base58
    fernet_key = _generate_fernet_key(os.getenv("MASTER"), os.getenv("SALT"))
    encrypted_private_key = _encrypt_private_key(account.private_key, fernet_key)
    wallet = client.query(
        q.create(
            q.collection("user"),
            {
                "data": {
                    "user_id": user_id,
                    "wallet_name": wallet_name,
                    "encrypted_private_key": encrypted_private_key,
                    "public_key": public_key,
                    "wallet_address": address,
                    "wallet_account_balance": 0.0,
                    "transactions": [],
                    "date_generated": time.time(),
                }
            },
        )
    )
    return True
