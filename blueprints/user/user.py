import datetime
import bcrypt
import pymongo
import os
import openai
from blueprints.getTokens import addEvent
from blueprints.ibm_connection import cos, cosReader
from blueprints.user.generate_slots import generate_slots
from bson import ObjectId
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from blueprints.database_connection import users, hospitals, appointments, doctors
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

user = Blueprint("user", __name__, template_folder="templates")
specialties = ['Cardiology', 'Dermatology', 'Endocrinology', 'Gastroenterology', 'General Practice', 'Infectious Diseases', 'Neurology', 'Oncology', 'Pediatrics', 'Psychiatry', 'Pulmonology', 'Radiology', 'Rheumatology']

@user.route('/')
def hello_world():
   return render_template('user/login.html')


# Route for user registration
@user.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        aadharnumber = request.form.get('aadharnumber')
        password = request.form.get('password') 
        name = request.form.get('name')
        phone = request.form.get('phone')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        
        #generating pem
        private_key_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.PKCS8,encryption_algorithm=serialization.NoEncryption())
        public_key_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo)
        
        # Validate required fields
        if not aadharnumber or not password or not name or not phone:
            return render_template('login.html', message='All Fields are required')

        # Check duplicate usernames
        existing_user = users.find_one({'aadharnumber': aadharnumber})

        if existing_user:
            return render_template('user/login.html', message='User Already exists')
    
        # Hash password 
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Insert user
        user = {
        'aadharnumber':aadharnumber,
        'name': name,
        'password': hashed_password,
        'phone': phone,
        'private_key': private_key_pem.decode('utf-8'),
        'public_key': public_key_pem.decode('utf-8'),
        }
        
        try:
            result = users.insert_one(user)
        
            if result.inserted_id:
                return redirect(url_for('user.user-dashboard'))
            else:
                return render_template('user/login.html', message='User not created')

        except Exception as e:
            print(e)
            return jsonify({'message': 'Unknown error'}), 500
    else:
        # GET request - show signup form
        return render_template('user/register.html')


@user.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        aadharnumber = request.form['aadharnumber']
        password = request.form['password']
        
        user = users.find_one({'aadharnumber': aadharnumber})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['aadharnumber'] = aadharnumber
            session['_id'] = str(user['_id'])
            return redirect(url_for('user.user_dashboard'))
        else:
            return render_template('user/login.html', message='Incorrect aadharnumber/password combination')
            
    return render_template('user/login.html')

@user.route('/search',methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    suggestions = get_autocomplete_suggestions(keyword)
    return jsonify(suggestions)

def get_autocomplete_suggestions(keyword):
    # Perform MongoDB query for autocomplete suggestions
    regex_pattern = f'.*{keyword}.*'  # Construct a regex pattern
    query = {'hospital_name': {'$regex': regex_pattern, '$options': 'i'}}  # Case-insensitive regex search
    projection = {'_id': 0, 'hospital_name': 1}  

    # Query the 'hospitals' collection for suggestions
    suggestions_cursor = hospitals.find(query, projection)
    
    # Convert the cursor to a list of dictionaries
    suggestions = list(suggestions_cursor)
    return suggestions


# user dashboard
@user.route('/user-dashboard',methods=['GET'])
def user_dashboard():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        user_id = users.find_one({'aadharnumber':session['aadharnumber']},"_id")
        userdata = users.find_one({'_id':user_id['_id']},{'password':0})
        query ={'user_id':user_id['_id']}
        res=[]
        appointments_data = appointments.find(query)
        appointments_data= list(appointments_data)
        for appointment_data in appointments_data:
            doctor_id = appointment_data['doctor_id']
            doctor_data = get_doc_details(doctor_id)
            
            combined_data = {
                'doctor': {
                    'name': doctor_data['name'],
                    'email': doctor_data['email'],
                    'hospital_name': doctor_data['hospital']
                },
                'appointment': {
                    'appointment_date': appointment_data['appointment_date'],
                    'appointment_time': appointment_data['appointment_time'],
                    'status': appointment_data['status'],
                    'issue': appointment_data['issue'],
                    'reviews': appointment_data['reviews'],
                }
            }
            res.append(combined_data)
    return render_template('user/user-dashboard.html',appointments=res,userdata=userdata)


@user.route('/my-appointments',methods=['GET'])
def my_appointements():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        user_id = users.find_one({'aadharnumber':session['aadharnumber']},"_id")
        query ={'user_id':user_id['_id']}
        res=[]
        appointments_data = appointments.find(query,{}).sort([("timestamp",pymongo.DESCENDING)])
        appointments_data= list(appointments_data)
        for appointment_data in appointments_data:
            doctor_id = appointment_data['doctor_id']
            doctor_data = get_doc_details(doctor_id)
            
            combined_data = {
                'doctor': {
                    'name': doctor_data['name'],
                    'email': doctor_data['email'],
                    'hospital_name': doctor_data['hospital_address'],
                    'location': doctor_data['location'],
                    # Other doctor fields
                },
                'appointment': {
                    'appointment_date': appointment_data['appointment_date'],
                    'appointment_time': appointment_data['appointment_time'],
                    # Other appointment fields
                }
            }
            
            res.append(combined_data)
        return render_template('user/my-appointments.html',appointments_data=res)
    
@user.route('/get_doc_details',methods=['GET'])
def get_doc_details(doctor_id):
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        doctor_details = doctors.find_one({'_id':doctor_id})
        return  doctor_details
@user.route('/my-reports',methods=['GET'])
def my_reports():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        user = users.find_one({'_id': ObjectId(session['_id'])})
        return render_template('user/my-reports.html', reports=user['pdfReports'])

@user.route('/my-profile',methods=['GET'])
def my_profile():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        user=users.find_one({'aadharnumber':session['aadharnumber']})
        PDFreports=[{'filetype':'x-ray','filename':'tdt.txt'},{'filetype':'prescription','filename':'tdt.txt'}] 
        return render_template('user/my-profile.html',reports=PDFreports ,user=user)
    
@user.route('/search_doctors',methods=['POST','GET'])
def search_docotors():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        hospital_name = request.form.get('hospital')
        location = request.form.get('location')
        symptoms = request.form.get('symptoms')
        # Create a query based on the provided criteria
        query = {
            'hospital': hospital_name,
            'location': location,
        }
        
        # Find doctors matching the query and retrieve their IDs
        doctors_cursor = doctors.find(query)
        doctors_cursor = list(doctors_cursor)
        hospitals_loc_data = get_hospitals_locations()
        hospitals_names = hospitals.distinct('hospital_name')
        # Extract doctor IDs from the cursor
        return render_template('user/doctors.html',doctors_data=doctors_cursor , hospitals_names=hospitals_names ,locations=hospitals_loc_data)

@user.route('/get-doctors',methods=['GET'])
def get_doctors():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        doctors_data = doctors.find().limit(100)
        doctors_data= list(doctors_data)
        hospitals_loc_data = doctors.distinct('location')
        hospitals_names = hospitals.distinct('hospital_name')
        return render_template('user/doctors.html',doctors_data=doctors_data , hospitals_names=hospitals_names ,locations=hospitals_loc_data)
@user.route('/prescriptions_list',methods=['GET','POST'])
def prescriptions_list():
     if request.method == 'POST':
        medicine_id = request.form['charge'].split(')')[0]
        days = request.form['days']
        evn = request.form.get("evn") != None
        aft = request.form.get("aft") != None
        mor = request.form.get("mor") != None

@user.route('/recommendMydoctor',methods=['GET','POST'])
def recommendMydoctor():
    if request.method=='POST':
        hospitals_loc_data = doctors.distinct('location')
        hospitals_names = hospitals.distinct('hospital_name')
        hospital_name = request.form['hospital']
        location = request.form['location']
        doctors_data = doctors.find().limit(100)
        doctors_data= list(doctors_data)
        symptoms = request.form.getlist('symptoms[]')
        if symptoms!=[]  and hospital_name != 'Select Hospital' and location!='Select Location':
            specialist = str(get_specialist(symptoms, session['age'], session['gender'])).strip()
            sorted_doctors= doctors.find({'hospital':hospital_name,'speciality': specialist,'location': location}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        elif symptoms!=[]  and location!='Select Location':
            specialist = str(get_specialist(symptoms, session['age'], session['gender'])).strip()
            sorted_doctors= doctors.find({'speciality': specialist,'location': location}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        elif  hospital_name !='Select Hospital' and location!='Select Location':
             sorted_doctors= doctors.find({'hospital':hospital_name,'location': location}).sort('recommendation_score',-1)
             sorted_doctors=list(sorted_doctors)
             return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        elif hospital_name != 'Select Hospital' and symptoms!=[]:
            specialist = str(get_specialist(symptoms, session['age'], session['gender'])).strip()
            sorted_doctors= doctors.find({'hospital':hospital_name,'speciality': specialist}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        
        elif symptoms!=[]:
            specialist = str(get_specialist(symptoms, session['age'], session['gender'])).strip()
            sorted_doctors= doctors.find({'speciality': specialist}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        elif hospital_name != 'Select Hospital':
            sorted_doctors= doctors.find({'hospital':hospital_name}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        elif location!='Selected Location':
            sorted_doctors=  doctors.find({'location': location}).sort('recommendation_score',-1)
            sorted_doctors=list(sorted_doctors)
            return render_template('user/doctors.html',doctors_data=sorted_doctors,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
        else:
            return render_template('user/doctors.html',doctors_data=doctors_data,hospitals_names=hospitals_names ,locations=hospitals_loc_data)
    

        

def get_specialist(symptoms, age, gender):
  openai.api_key = "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"
  prompt = f"Based on these symptoms: {symptoms}, for a {gender} aged {age}, the most accurate initially needed medical specialty from this list: {specialties} is:"

  response = openai.Completion.create(
    engine="text-davinci-002",
    prompt=prompt,
    temperature=0.5, 
    max_tokens=60,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )

  return response.choices[0].text.strip()


@user.route('/book_appointment/<doctor_id>/<user_id>',methods=['GET'])
def book_appointment(doctor_id, user_id):
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        doctor_data = get_doc_details(ObjectId(doctor_id))
        return render_template('user/book-appointment.html',doctor_data=doctor_data)


@user.route('/logout',methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@user.route('/get_hospitals_locations',methods=['GET'])
def get_hospitals_locations():
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        hospitals_data = hospitals.distinct('location')
        hospitals_loc_data= hospitals_data
        return hospitals_loc_data


@user.route('/confirm_booking/<string:doctor_id>', methods=['POST'])
def confirm_booking(doctor_id):
    if 'aadharnumber' in session:
        accessToken = doctor_id + session['_id']
        doctor_id = ObjectId(doctor_id)
        doctor_data = get_doc_details(ObjectId(doctor_id))
        user_id = ObjectId(session['_id'])
        selected_date = request.form['appointment_date']
        selected_time_slot = request.form['time_slot']  
        reason = request.form['reason']
        # Convert selected date and time to datetime objects
        selected_datetime = datetime.datetime.strptime(selected_date + ' ' + selected_time_slot, '%Y-%m-%d %I:%M %p')
        current_datetime = datetime.datetime.now()

        # Calculate the difference in days between selected date and current date
        days_difference = (selected_datetime.date() - current_datetime.date()).days
        # Check booking conditions
        if days_difference <= 15:
            if days_difference >= 0:
                # Booking is within 15 days, proceed with time check
                if selected_datetime > current_datetime + datetime.timedelta(minutes=10):
                    start_time = datetime.datetime.strptime(selected_time_slot, "%I:%M %p")
                    end_time = start_time + datetime.timedelta(minutes=30)
                    _ ,start_time = str(start_time).split()
                    _ ,end_time = str(end_time).split()
                    start_time = start_time[:-3]
                    end_time = end_time[:-3]
                    start_datetime = datetime.datetime.strptime(selected_date + " " + str(start_time), "%Y-%m-%d %H:%M").isoformat() + "+05:30"
                    end_datetime = datetime.datetime.strptime(selected_date + " " + str(end_time), "%Y-%m-%d %H:%M").isoformat() + "+05:30"
                    location = doctor_data['hospital_address'] + " " + doctor_data['location']
                    description = "Appointment with doctor "+ doctor_data['name'] + " (" + doctor_data['speciality'] +") @ " + str(selected_time_slot)
                    event = {
                        "summary": "Doctor Appointment",
                        "location": location,
                        "description": description,
                        
                        "start": {
                            "dateTime": start_datetime, 
                            "timeZone": "Asia/Kolkata"
                        },
                        
                        "end": {
                            "dateTime": end_datetime,
                            "timeZone": "Asia/Kolkata"
                        },

                        "reminders": {
                            "useDefault": False,
                            "overrides": [
                            {"method": "email", "minutes":180},
                            {"method": "popup", "minutes": 30}
                        ]
                        },
                        "visibility":"public",
                        "sendNotifications": True,
                        "sendUpdates": "all"
                    }

                    event_id  = addEvent(session['_id'],1,event=event)
                    booking_data = {
                        'user_id': user_id,
                        'doctor_id': doctor_id,
                        'appointment_date': selected_date,
                        'appointment_time': selected_time_slot,
                        'accessToken': accessToken,
                        'accessed':'0',
                        'timestamp': datetime.datetime.now(),
                        'issue': reason,
                        'reviews': '',
                        'notes': [],
                        'status': 'booked',
                        'lab_tests': [],
                        'lab_report': [],
                        'calendar_event_id':str(event_id)
                    }
            
                    # Insert the booking data into the database
                    appointments.insert_one(booking_data)

            
                    return render_template('user/book-appointment.html',message ="Appointment confirmed successfully!",type="success", doctor_data = doctor_data)
                else:
                    return render_template('user/book-appointment.html',message ="You can only book appointments that are more than 10 minutes away from the current time.", type="error" ,doctor_data = doctor_data)
            else:
                return render_template('user/book-appointment.html',message ="You cannot book appointments for a past date.", type="error" ,doctor_data = doctor_data)
        else:
            return render_template('user/book-appointment.html',message ="You can only book appointments up to 15 days from the current date", type="error" ,doctor_data = doctor_data)
    else:
        return redirect(url_for('login'))

@user.route('/check_appointments/<string:doctor_id>/<string:selected_date>/<int:dayOfWeek>')
def check_appointments(doctor_id, selected_date, dayOfWeek):
    days_of_week = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    doctor_id = ObjectId(doctor_id)
    get_schedule = doctors.find_one({"_id":doctor_id},{"schedule":1})
    schedule = get_schedule['schedule'][days_of_week[dayOfWeek]]
    if 'surgery' in schedule:
        del schedule['surgery']
    available_slots = generate_slots(schedule, selected_date)
    get_appointments = list(appointments.find({"doctor_id":doctor_id,"appointment_date":selected_date},{"appointment_time":1, "_id":0}))
    get_appointments = [appointment['appointment_time'] for appointment in get_appointments]
    return jsonify({"available_slots":available_slots, "booked_slots":get_appointments})

@user.route('/already_in_appointment/<string:doctor_id>/<string:selected_date>')
def already_in_appointment(doctor_id, selected_date):
    doctor_id = ObjectId(doctor_id)
    if 'aadharnumber' in session:
        user_id = users.find_one({"aadharnumber":session['aadharnumber']},{"_id":1})
    else:
        return redirect(url_for('login'))
    get_appointment = list(appointments.find({"user_id":user_id,"doctor_id":doctor_id,"appointment_date":selected_date},{}))
    if len(get_appointment) >= 1:
        return jsonify({"message": "True"})
    return jsonify({"message":"False"})

@user.route('/doctor-profile/<string:doctor_id>',methods=['GET'])
def doctor_profile(doctor_id):
    if 'aadharnumber' not in session:
        return redirect(url_for('login'))
    else:
        doctor_data = get_doc_details(ObjectId(doctor_id))
        return render_template('user/doctor-profile.html',doctor_data=doctor_data)
    
# ----------------------==========Upload File =========------------------------

@user.route('/upload', methods=['POST'])
def upload_file():
    report_type = request.form['report_type']
    uploaded_file = request.files['file']

    if uploaded_file:
        user_name = session['_id']
        filename = f"{user_name}_{report_type}.pdf"

        # Save the uploaded file in the current folder
        uploaded_file.save(filename)

        try:
            # Upload the file to COS
            cos.upload_file(Filename=filename, Bucket='healthconnectibm', Key=filename)
        except Exception as e:
            os.remove(filename)
            return f"Error uploading to COS: {e}"
        else:
            # Remove the uploaded file after successful upload
            os.remove(filename)

            report_info = {'reportType': report_type, 'filename': filename}
            query = {"_id": ObjectId(session['_id'])}
            update = {"$push": {"pdfReports": report_info}}
            users.update_one(query, update)
            return render_template('user/my-reports.html',message ="File uploaded Succesfully !",type="success", reports = users.find_one(query)['pdfReports'])
    else:
        return render_template('user/my-reports.html',message ="File not uploaded",type="error", reports = users.find_one(query)['pdfReports'])

    
@user.route('/viewreports')
def view_reports():
  if '_id' in session:
    user = users.find_one({'_id': ObjectId(session['_id'])})
    if user:
      return render_template('my-reports.html', reports=user['pdfReports'])
  else: 
    return redirect(url_for('login'))
  
@user.route('/display_pdf/<filename>')
def display_pdf(filename):
    bucket_name = 'healthconnectibm'
    key_name = filename
    http_method = 'get_object'
    expiration = 600
    # Generate pre-signed URL that is valid for 60 seconds
    try:
        signedUrl = cosReader.generate_presigned_url(http_method, Params={'Bucket': bucket_name, 'Key': key_name}, ExpiresIn=expiration)
    except Exception as e:
        print(e)
        return "Cannot load data"
    return render_template('user/display-report.html', pdfUrl = signedUrl)

@user.route('/fit_data')
def fit_data():
    today = datetime.datetime.now()
    value = addEvent(session['_id'],2,date=today)
    return value