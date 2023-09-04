
from __future__ import print_function
import datetime
import requests
import json
from bson import ObjectId
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from blueprints.database_connection import tokens

creds = None
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar','https://www.googleapis.com/auth/fitness.activity.read','https://www.googleapis.com/auth/fitness.body.read',
          'https://www.googleapis.com/auth/fitness.heart_rate.read']


def getSteps(date):
    global creds
    headers = {
            'Authorization': 'Bearer ' + str(creds.token) 
        }
    params = {
    'userId': 'me',
    'datasetId': date
    }
    start = int(date.timestamp()) * 1000
    end = start + 86400000 

    # API request body
    body = {
        "aggregateBy": [{
        "dataTypeName": "com.google.step_count.delta",
        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        }],
        "bucketByTime": { "durationMillis": 86400000 },
        "startTimeMillis": start,
        "endTimeMillis": end 
    }

    # Make POST request
    url = 'https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate'
    response = requests.post(url, params=params, json=body, headers=headers)
    # Print steps for date
    steps = response.json()['bucket'][0]['dataset'][0]['point'][0]['value'][0]['intVal']
    return steps

def addEvent(id, what, event=None,date=None):
    global creds
    jsondata = tokens.find_one({"userID":ObjectId(id)},{'_id':0,'userID':0})
    if jsondata is not None:
        jsondata = json.loads(json.dumps(jsondata,default=lambda o: o.__dict__))
        creds = Credentials.from_authorized_user_info(jsondata, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            updated = tokens.update_one({'userID':ObjectId(id)},{'$set':{'token':creds.token}})
            if updated:
                print("Updated")
            else:
                print("No")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'blueprints/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            creds_json = json.loads(creds.to_json())
            creds_json["userID"] = ObjectId(id)
            creds_json["streak"] = -1
            tokens.insert_one(creds_json)
        
    if what == 1:
        try:
            service = build('calendar', 'v3', credentials=creds)
            events = service.events().insert(calendarId='primary', body=event).execute()
            return str(events.get('id'))
        except HttpError as error:
            print('An error occurred: %s' % error)
    elif what == 2:
        stepsDict = {}
        calories_dict = {}
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0) 
        week_ago = today - datetime.timedelta(days=7)
        dates = []
        for i in range(7):
            date = week_ago + datetime.timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))

        end = int(today.timestamp()) * 1000
        start = int(week_ago.timestamp()) * 1000

        # API endpoint and headers
        url = 'https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate'
        headers = {
            'Authorization': 'Bearer ' + str(creds.token)
        }

        # Request body
        request = {
        'aggregateBy': [{
            'dataSourceId': 'derived:com.google.step_count.delta:com.google.android.gms:estimated_steps',
            'dataTypeName': 'com.google.step_count.delta'
        }],
        'bucketByTime': {'durationMillis': 86400000},
        'startTimeMillis': start,
        'endTimeMillis': end 
        }

        # Make POST request
        response = requests.post(url, json=request, headers=headers).json()

        # Print buckets
        for i,bucket in enumerate(response['bucket']):
            steps = bucket['dataset'][0]['point'][0]['value'][0]['intVal']
            stepsDict[dates[i]] = steps

        request = {
        'aggregateBy': [{ 
            'dataTypeName': 'com.google.calories.expended',
            'dataSourceId': 'derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended'
        }],

        'bucketByTime': {'durationMillis': 86400000},
        'startTimeMillis': start,
        'endTimeMillis': end 
        }

        # Make API request
        response2 = requests.post(url, json=request, headers=headers)
        response2 = response2.json()
        # Process response
        for i,bucket in enumerate(response2['bucket']):
            date = dates[i]
            bpm = bucket['dataset'][0]['point'][0]['value'][0]['fpVal']
            calories_dict[date] = bpm

        url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
        today = datetime.datetime.now()
        start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = today.replace(hour=23, minute=59, second=59, microsecond=999)

        # Convert timestamps to milliseconds since the epoch
        start_time_millis = int(start_of_day.timestamp()) * 1000
        end_time_millis = int(end_of_day.timestamp()) * 1000

        # Define the request payload
        request = {
            "aggregateBy": [{
                "dataTypeName": "com.google.step_count.delta",
                "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
            }],
            "bucketByTime": { "durationMillis": 86400000 },
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        response3 = requests.post(url, json=request, headers=headers)
        response3 = response3.json()
        todaySteps = response3["bucket"][0]["dataset"][0]["point"][0]["value"][0]["intVal"]

        return [stepsDict,calories_dict, todaySteps]
