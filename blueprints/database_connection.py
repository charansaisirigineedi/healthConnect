from pymongo import MongoClient
from pymongo.server_api import ServerApi
from blueprints.confidential import MONGOURI
import logging

client = MongoClient(MONGOURI, server_api=ServerApi('1'))

try: 
    client.admin.command('ping')
    logging.info("Connected to MONGOdb")

    db = client['healthConnectdb']
    
    appointments = db['appointments']
    blogVar = db['blogs']
    doctors = db['doctor']
    tokens = db['googleTokens']
    hospitals= db['hospitals']
    labs = db['labs']
    logger = db['logs']
    medicines = db['medicines']
    users = db['users']

except Exception as e:
    logging.error(e)

