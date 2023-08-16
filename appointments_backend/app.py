from datetime import datetime
import json
import bcrypt
from bson import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient 
from pymongo.server_api import ServerApi
from generate_Slots import generate_slots

app = Flask(__name__)
app.secret_key = 'somesecretkey'

client = MongoClient("mongodb+srv://charanmcr:Charansai20020902@healthconnect.bfcrznb.mongodb.net/?retryWrites=true&w=majority", server_api=ServerApi('1'))

try: 
    client.admin.command('ping')
    print("Connected to MongoDB!")
except Exception as e:
    print(e)

db = client['healthConnectdb']
users = db['users']
doctors = db['doctor']
appoint = db['appointments']

@app.route('/')
def index():
    return "Hello Word!!!"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']        
        result = users.find_one({"aadharnumber": username},{})
        print(result['_id'])
        if result:
            session['ID'] = str(result['_id'])
            print(session['ID'])
            return redirect(url_for('dashboard'))                        
        else:
            return "Invalid"
    else:
        return render_template('index.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'ID' in session:
        fetch_doctor = doctors.find().limit(10)
        return render_template('dashboard.html', doctor = fetch_doctor)
    else:
        return redirect(url_for('login'))
    
@app.route('/book_appointment/<string:doctor_id>')
def book_appointment(doctor_id):
    if 'ID' in session:
        doctor_id = ObjectId(doctor_id)
        doctor = doctors.find_one({"_id": doctor_id})
        if doctor:
            return render_template('bookings.html', doctor=doctor)
        else:
            return "Doctor not found"
    else:
        return redirect(url_for('login'))
    
@app.route('/confirm_booking/<string:doctor_id>', methods=['POST'])
def confirm_booking(doctor_id):
    if 'ID' in session:
        doctor_id = ObjectId(doctor_id)
        user_id = ObjectId(session['ID'])
        selected_date = request.form['appointment_date']
        selected_time_slot = request.form['time_slot']
        
        booking_data = {
            'user_id': user_id,
            'doctor_id': doctor_id,
            'appointment_date': selected_date,
            'appointment_time': selected_time_slot,
            'timestamp': datetime.now()
        }
        
        # Insert the booking data into the database
        appoint.insert_one(booking_data)
        
        return "Appointment confirmed successfully!"
    else:
        return redirect(url_for('login'))
    
@app.route('/check_appointments/<string:doctor_id>/<string:selected_date>/<int:dayOfWeek>')
def check_appointments(doctor_id, selected_date, dayOfWeek):
    days_of_week = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    doctor_id = ObjectId(doctor_id)
    get_schedule = doctors.find_one({"_id":doctor_id},{"schedule":1})
    schedule = get_schedule['schedule'][days_of_week[dayOfWeek]]
    if 'surgery' in schedule:
        del schedule['surgery']
    available_slots = generate_slots(schedule)
    get_appointments = list(appoint.find({"doctor_id":doctor_id,"appointment_date":selected_date},{"appointment_time":1, "_id":0}))
    get_appointments = [appointment['appointment_time'] for appointment in get_appointments]
    return jsonify({"available_slots":available_slots, "booked_slots":get_appointments})

if __name__ == '__main__':
    app.run(debug=True)
