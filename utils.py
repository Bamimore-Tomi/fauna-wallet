import os, json, base64, base58, time, io, string, random
from typing import Optional
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from faunadb.errors import NotFound
from tronapi import Tron
from tronapi.common.account import PrivateKey
from dotenv import load_dotenv
import telegram, qrcode
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


def _decrypt_private_key(hash, key: str) -> str:
    decryptor = Fernet(key)
    private_key = decryptor.decrypt(hash.encode())
    return private_key.decode()


def save_user(client: FaunaClient, data: dict):
    user = client.query(
        q.create(
            q.collection("user"),
            {"data": data},
        )
    )


def get_wallets(client: FaunaClient, user_id: int, wallet_name: Optional[str] = None):
    wallets = client.query(
        q.paginate(q.match(q.index("wallet_index"), user_id), size=100_000)
    )
    if len(wallets["data"]) < 1:
        raise errors.WalletNotFound

    wallets_data = [
        q.get(q.ref(q.collection("wallet"), wallet.id())) for wallet in wallets["data"]
    ]
    wallets_data = client.query(wallets_data)
    result = []
    if wallet_name != None:
        for i in wallets_data:
            if i["data"]["wallet_name"] == wallet_name:
                i["data"]["ref"] = i["ref"].id()
                wallet = i["data"]
                return wallet
        raise errors.WalletNotFound
    else:
        for i in wallets_data:
            i["data"]["ref"] = i["ref"].id()
            result.append(i["data"])

    return result


def generate_wallet_menu(
    client: FaunaClient,
    user_id: int,
    with_address: Optional[bool] = False,
    with_ref: Optional[bool] = False,
):
    data = get_wallets(client, user_id)
    menu = keyboards.wallet_menu(data, with_address=with_address, with_ref=with_ref)
    return menu


def generate_wallet_keyboard(client: FaunaClient, user_id: int):
    data = get_wallets(client, user_id)
    keyboard = keyboards.wallet_keyboard(data)
    return keyboard


def _validate_address(address: str):
    tron = Tron()
    validate = tron.trx.validate_address(address)
    if validate.get("result") == False:
        raise ValueError(validate.get("message"))
    return address


def get_balance(address: str):
    tron = Tron()
    return tron.fromSun(tron.trx.get_balance(address))


def _get_qr_code(wallet_address: str):
    img = qrcode.make(wallet_address)
    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format=img.format)
    imgByteArr = imgByteArr.getvalue()
    # return base64.encodebytes(imgByteArr)
    return imgByteArr


def get_wallet_detail(client: FaunaClient, user_id: int, wallet_name: str):
    wallet = get_wallets(client, user_id, wallet_name)
    qr_byte = _get_qr_code(wallet["wallet_address"])
    file_name = random_string(length=5) + ".png"
    open(file_name, "wb").write(qr_byte)
    stream = open(file_name, "rb")
    os.remove(file_name)
    return wallet, stream


def create_wallet(client: FaunaClient, user_id: int, wallet_name: str) -> bool:
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
    save_wallets(client)
    return address.base58


def delete_wallet(client: FaunaClient, user_id: int, wallet_ref: str):
    try:
        client.query(q.delete(q.ref(q.collection("wallet"), wallet_ref)))
    except NotFound:
        raise errors.WalletNotFound
    except Exception as e:
        print(e)


def save_wallets(client: FaunaClient):
    wallets = client.query(q.paginate(q.documents(q.collection("wallet"))))
    query = [
        q.get(q.ref(q.collection("wallet"), wallet.id())) for wallet in wallets["data"]
    ]
    data = client.query(query)
    wallets = []
    for i in data:
        i["data"]["ref"] = i["ref"].id()
        wallets.append(i["data"])
    f = open("wallets.json", "w")
    json.dump(wallets, f)


def blockchain_runner():
    # This function runs throgh the block chain and check for transactions in know wallets
    # It adds and subtracts to wallet balance if a transaction is made from or two a wallet
    client = load_db()
    tron = Tron()

    while True:
        data = json.load(open("wallets.json"))
        last_block = tron.trx.get_confirmed_current_block()
        # last_block = json.load(open("well.json"))
        transactions = last_block.get("transactions")
        for i in transactions:
            values = i.get("raw_data").get("contract")[0].get("parameter").get("value")
            if values["owner_address"] in [i["wallet_address"]["hex"] for i in data]:
                tx_id = i["txID"]
                wallet = [
                    i
                    for i in data
                    if i["wallet_address"]["hex"] == values["owner_address"]
                ][0]
                record_transaction(
                    client,
                    wallet,
                    "debit",
                    values["amount"],
                    values["owner_address"],
                    tx_id,
                )
            else:
                try:
                    if values["to_address"] in [
                        i["wallet_address"]["hex"] for i in data
                    ]:
                        tx_id = i["txID"]
                        wallet = [
                            i
                            for i in data
                            if i["wallet_address"]["hex"] == values["to_address"]
                        ][0]
                        record_transaction(
                            client,
                            wallet,
                            "credit",
                            values["amount"],
                            values["owner_address"],
                            tx_id,
                        )
                except:
                    continue


def record_transaction(
    client: FaunaClient, wallet: dict, type_: str, amount: int, address: str, tx_id: str
):
    tron = Tron()
    bot = telegram.Bot(token=os.getenv("TOKEN"))
    wallet = get_wallets(client, wallet["user_id"], wallet_name=wallet["wallet_name"])
    prev_transactions = wallet["transactions"]
    balance = wallet["wallet_account_balance"]

    if type_ == "credit":
        balance += amount
    if type_ == "debit":
        balance -= amount

    new = {
        "type": type_,
        "address": tron.address.from_hex(address).decode(),
        "amount": amount,
        "tx_id": tx_id,
        "time": time.time(),
    }
    prev_transactions.append(new)
    client.query(
        q.update(
            q.ref(q.collection("wallet"), wallet["ref"]),
            {
                "data": {
                    "transactions": prev_transactions,
                    "wallet_account_balance": balance,
                }
            },
        )
    )
    save_wallets(client)
    bot.send_message(
        chat_id=wallet["user_id"],
        text=f"Transaction Alert\n\nType: {type_}\nAmount: {amount}\nAddress: {tron.address.from_hex(address).decode()}",
    )


def send_trx(sender_private_key: str, reciever_address: str, amount: int):
    fernet_key = _generate_fernet_key(os.getenv("MASTER"), os.getenv("SALT"))
    private_key = _decrypt_private_key(sender_private_key, fernet_key)
    tron = Tron()
    tron.private_key = private_key
    tron.default_address = tron.address.from_private_key(tron.private_key)["base58"]
    reciever_address = _validate_address(reciever_address)
    balance = get_balance(tron.default_address["base58"])
    print(balance)
    if balance == 0 or amount > balance:
        raise errors.InsufficientBalance
    transaction = tron.trx.send(reciever_address, amount)
    return True


if __name__ == "__main__":
    client = load_db()
    # print(generate_wallet_menu(client, 1766860738))
    # save_wallets(client)
    send_trx(
        "gAAAAABg3eVzHt6OCKCv-7MptG3oLKcZxE3npAX3-Xe8LubcKHLs0YJ-El0QwjmdO-7hxjCN1ae3JglhEWf7aaZ3SZRpgiRZHG_SjhJCTQdfu2l7RUKOP3bfNfsRNNWysMwdDwSo4KRpagMyUMNhnfppUX-Ph21dgioq7IHmQZuh3w_fUz96Hjo=",
        "TNvuB92YzbdncYhteNX2TPGmX61QxQBDsv",
        7,
    )
