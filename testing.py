from bson import ObjectId
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
    doctors = db['doctor']
    tokens = db['googleTokens']
    hospitals= db['hospitals']
    labs = db['labs']
    medicines = db['medicines']
    users = db['users']

except Exception as e:
    logging.error(e)

dicid = '64dbaff3d3e3b71e8a9dfe6f'

# result  = doctors.find_one({'_id':ObjectId(dicid)})
# print(result)
# hosid = result['hospitalID']
# hosdetails = hospitals.find_one({'_id':ObjectId(hosid)})
# print(hosdetails)
pipeline = [{"$match": {"_id": ObjectId(dicid)}}, {"$lookup": {"from": "hospitals", "localField": "hospitalID", "foreignField": "_id", "as": "hospital"}}, {"$unwind": "$hospital"}, {"$project": {"_id": 0, "doctor": "$$ROOT", "hospital": "$hospital"}}]


result = doctors.aggregate(pipeline).next()

doctor_details = result['doctor']
del doctor_details['hospital']
doctor_details["hospital"] = result["hospital"]["hospital_name"]
doctor_details["hospital_address"] = result["hospital"]["address"]
doctor_details["location"] = result["hospital"]["location"]
print(doctor_details)