from pymongo import MongoClient 
from pymongo.server_api import ServerApi


client = MongoClient("mongodb+srv://charanmcr:Charansai20020902@healthconnect.bfcrznb.mongodb.net/?retryWrites=true&w=majority", server_api=ServerApi('1'))

db = client['healthConnectdb']
users = db['users']
tokens = db['googleTokens']