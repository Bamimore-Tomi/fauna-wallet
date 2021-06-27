import os, json, base64, time, io, qrcode, string, random
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
    if len(text.split(" ")) > 1:
        return False, None
    return True, text.lower()


def random_string(length=12):
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    letters = lowercase + uppercase
    secret = "".join(random.choice(letters) for i in range(length))
    return secret


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


def get_wallets(client, user_id, wallet_name=None):
    wallets = client.query(q.paginate(q.match(q.index("wallet_index"), user_id)))
    if len(wallets["data"]) < 1:
        raise errors.WalletNotFound

    wallets_data = [
        q.get(q.ref(q.collection("wallet"), wallet.id())) for wallet in wallets["data"]
    ]
    wallets_data = client.query(wallets_data)
    if wallet_name != None:
        for i in wallets_data:
            if i["data"]["wallet_name"] == wallet_name:
                wallet = i["data"]
                return wallet
        raise errors.WalletNotFound
    return [i["data"] for i in wallets_data]


def generate_wallet_menu(client, user_id):
    data = get_wallets(client, user_id)
    menu = keyboards.wallet_menu(data)
    return menu


def generate_wallet_keyboard(client, user_id):
    data = get_wallets(client, user_id)
    keyboard = keyboards.wallet_keyboard(data)
    return keyboard


def _validate_address(address):
    tron = Tron()
    validate = tron.trx.validate_address(address)
    if validate.get("result") == False:
        raise ValueError(validate.get("message"))
    return address


def get_balance(address):
    tron = Tron()
    return tron.fromSun(tron.trx.get_balance(address))


def send_trx(sender_private_key, reciever_address, amount):
    fernet_key = _generate_fernet_key(os.getenv("MASTER"), os.getenv("SALT"))
    private_key = _decrypt_private_key(sender_private_key, fernet_key)
    tron = Tron()
    tron.private_key = private_key
    tron.default_address = tron.address.from_private_key(tron.private_key)["base58"]
    reciever_address = _validate_address(reciever_address)
    balance = get_balance(tron.default_address)
    if amount > balance:
        raise errors.InsufficientBalance
    transaction = tron.trx.send(reciever_address, amount)
    return True


def _get_qr_code(wallet_address):
    img = qrcode.make(wallet_address)
    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format=img.format)
    imgByteArr = imgByteArr.getvalue()
    # return base64.encodebytes(imgByteArr)
    return imgByteArr


def get_wallet_detail(client, user_id, wallet_name):
    wallet = get_wallets(client, user_id, wallet_name)
    qr_byte = _get_qr_code(wallet["wallet_address"])
    file_name = random_string(length=5) + ".png"
    open(file_name, "wb").write(qr_byte)
    stream = open(file_name, "rb")
    os.remove(file_name)
    return wallet, stream


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
    # print(generate_wallet_menu(client, 1766860738))
    get_wallet_detail(client, 1766860738, "xoxo")
