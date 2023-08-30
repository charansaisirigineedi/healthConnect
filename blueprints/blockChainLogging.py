import hashlib
import datetime
from blueprints.database_connection import logger

def generate_hash(message):
    sha = hashlib.sha256()    
    sha.update(message.encode('utf-8'))
    return sha.hexdigest()

def generate_genesis_block():
    current_timestamp = datetime.datetime.now()
    timestamp = str(current_timestamp.strftime("%Y-%m-%d %H:%M:%S"))
    content = "HealthConnect Application Genesis Block"
    message = timestamp + ": " + content 
    prev_hash = generate_hash(content)
    current_hash = generate_hash(message + str(prev_hash))
    genesis_block = {
        'timestamp': timestamp,
        'blockMessage': message,
        'prevHash':prev_hash,
        'blockHash': current_hash
    }
    logger.insert_one(genesis_block)
    return current_hash

def getPrevHash():
    count = list(logger.find().sort('timestamp', -1).limit(1))
    return count[0]['blockHash'] if len(count) == 1 else generate_genesis_block()

def blockChain(message):
    current_timestamp = datetime.datetime.now()
    timestamp = str(current_timestamp.strftime("%Y-%m-%d %H:%M:%S"))
    message = timestamp + ": " + message
    prev_hash = getPrevHash()
    current_hash = generate_hash(str(message)+str(prev_hash))
    doc = {
        'timestamp': timestamp,
        'blockMessage':  message,
        'prevHash': prev_hash,
        'blockHash': current_hash
    }
    logger.insert_one(doc)