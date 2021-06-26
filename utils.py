import os, json
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from dotenv import load_dotenv

def load_db():
    load_dotenv()
    client = FaunaClient(secret=os.getenv("FAUNA-KEY"))
    return client

def load_messages():
    f = open("messages.json","r")
    messages = json.load(f)
    return messages
