from datetime import datetime
from bson import ObjectId
from flask import Flask, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from confidential import REDIS_HOST, REDIS_PADDWORD, URI
import redis

app = Flask(__name__)
app.secret_key = "somesecretkey"

client = MongoClient(URI, server_api=ServerApi('1'))

try: 
    client.admin.command('ping')
    print("Connected to MongoDB!")
except Exception as e:
    print(e)

db = client['healthConnectdb']
users = db['users']
doctors = db['doctor']
appoint = db['appointments']

r = redis.Redis(
  host=REDIS_HOST,
  port=12013,
  password=REDIS_PADDWORD)


@app.route('/')
def hello():
    return "Hello, Redis"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        username = ObjectId(username)      
        result = doctors.find_one({"_id": username},{})
        if result:
            session['ID'] = str(result['_id'])
            return redirect(url_for('dashboard'))                        
        else:
            return "Invalid"
    else:
        return render_template('index.html')
    
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'ID' in session:
        tdate = datetime.now().strftime('%Y-%m-%d')
        doctor_id = ObjectId(session['ID'])
        fetch_appointments = appoint.find({'doctor_id': doctor_id, 'appointment_date': tdate})
        return render_template('dashboard.html', appointments = fetch_appointments, tdate = tdate)
    else:
        return redirect(url_for('login'))
    
@app.route('/view_details', methods=['GET'])
def view_details():
    message = ''
    appointment_id = request.args.get('appointment_id')
    user_id = request.args.get('user_id')
    access_token = request.args.get('access_token')
    appointment_id_2 = ObjectId(appointment_id)
    fetch_access = appoint.find_one({'_id':appointment_id_2},{'_id':0,'accessed':1})
    accessed = fetch_access['accessed']
    if not r.get(appointment_id) and accessed == '1':
        r.set(appointment_id, access_token, ex=30)
        appoint.update_one({'_id':appointment_id_2},{'$set':{'accessed':'0'}})
    elif not r.get(appointment_id) and accessed == '0':
        message = f"Cannot access details for User ID: {user_id}. Token Expired"
        return render_template('details.html', message=message)
    message = f"Viewing details for User ID: {user_id}, Access Token: {access_token}"
    return render_template('details.html', message=message)

if __name__ == '__main__':
    app.run()
