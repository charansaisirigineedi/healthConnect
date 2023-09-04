import random
import bcrypt
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from blueprints.database_connection import hospitals, doctors, appointments, users
from blueprints.redis_connection import r as redisCon

hospital = Blueprint("hospital",__name__,template_folder="templates")

@hospital.before_request
def check_session():
    if request.endpoint not in ['hospital.hospital_register', 'hospital.hospital_login'] and '_id' not in session:
        return redirect(url_for('hospital.hospital_login'))


@hospital.route('/hospital_register', methods=['GET', 'POST'])
def hospital_register():
    if request.method =="POST":
        hospital_name = request.form.get('d-name')
        location = request.form.get('location')
        password = request.form.get('d-password')
        phone = request.form.get('phone')
        address = request.form.get('address')
        hospital_username = [word[0].upper() for word in hospital_name.split()]
        hospital = {
            'hospital_name': hospital_name,
            'username' : hospital_username,
            'location': location,
            'password': password,
            'phone': phone,
            'address': address,
            'type' : 'hospitals'
        }
        try:
            result = hospitals.insert_one(hospital)
            if result.inserted_id:
                return redirect(url_for('hospital.hospital_dashboard') )
            else:
                return render_template('hospital/hospital-login.html', message='User not created')
            
        except Exception as e:
            print(e)
            return jsonify({'message': 'Unknown error'})
    else:
        # GET request - show signup form
        return render_template('hospital/hospital-register.html')

@hospital.route('/hospital_login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == "POST":
        hospital_name= request.form.get('d-email')
        password = request.form.get('d-password')
        hospital = hospitals.find_one({'username': hospital_name})
        print(hospital)
        if hospital and password == hospital['password']:
            session['_id'] = str(hospital['_id'])
            session['username']=hospital['hospital_name']
            return redirect(url_for('hospital.hospital_dashboard'))
        else:
            return render_template('hospital/hospital-login.html', message='Incorrect aadharnumber/password combination')
    else:
        return render_template('hospital/hospital-login.html')

@hospital.route('/hospital_dashboard',methods=['GET'])
def hospital_dashboard():
    if  '_id' in session:
        if request.args.get('message'):
            message = request.args.get('message')
        hospital_details = hospitals.find_one({'_id': ObjectId(session['_id'])})    
        doc_details = doctors.find({'hospitalId': ObjectId(session['_id']) , 'availability': 1})
        doc_details = list(doc_details)
        res=[]
        for i in doc_details:
            doctor_id = i['_id']
            
            # Find appointments for the current doctor
            appointments_data = list(appointments.find({'doctor_id': doctor_id , 'appointment_date' : datetime.now().strftime("%Y-%m-%d") , 'status' : 'booked'}))
            patients_count = len(list(appointments.find({'doctor_id': doctor_id })))
            if appointments_data:
                user_id = appointments_data[0]['user_id']
                
                # Find user details based on user_id from the appointments data
                user_details = list(users.find({'_id': user_id}, {'name': 1, 'aadharnumber': 1, '_id': 1}))
                
                if user_details:
                    # Merge user details into appointments_data
                    appointments_data[0]['user_details'] =user_details[0]
                    appointments_data[0]['doctor_details']=i
                    
                    # Append combined data to the result list
                    res.append(appointments_data)
        if request.args.get('message') != None:
            return render_template('hospital/hospital-dashboard.html',hospital_details=hospital_details , appointments_data = res , appointments_count=len(appointments_data) , doctor_count =len(doc_details) , patients_count = patients_count , message = message)   
        else:
            return render_template('hospital/hospital-dashboard.html',hospital_details=hospital_details , appointments_data = res , appointments_count=len(appointments_data) , doctor_count =len(doc_details) , patients_count = patients_count )   

@hospital.route('/hospital-approve-appointments/<app_id>', methods=['GET'])
def hospital_approve_appointments(app_id):
    if '_id' in session:
        query = {'_id': ObjectId(app_id)}
        print(query)
        update_data = {'$set': {'status': 'confirmed'}}
        update_result = appointments.update_one(query, update_data)

        if update_result.modified_count > 0:
            # Document was updated
            appointments_data = appointments.find({'hospital_id': ObjectId(session['_id'])})
            return redirect(url_for('hospital.hospital_dashboard', message='Success'))
        else:
            # Document was not updated
            return redirect(url_for('hospital.hospital_dashboard', message="There was an error approving the appointment"))
   
@hospital.route('/generate_token/<ap_id>',methods=['GET'])
def generate_token(ap_id):
    if '_id' in session :
        key_name = random.randint(1000, 9999)
        access_token = redisCon.get(ap_id)
        if not access_token:
            access_token = key_name  # Define how you get the access token
            redisCon.set(ap_id, access_token, ex=600) 
    return render_template('hospital/authentication.html',app_id =ap_id)

@hospital.route('/validate_access_token/<ap_id>',methods=['POST' , 'GET'])
def validate_access_token(ap_id):
    if '_id' in session:
        
        token = int(request.args.get('token'))
        if redisCon.get(ap_id) is None :
            return render_template('hospital/authentication.html', error_msg = 'Token Expired')
        if int(redisCon.get(ap_id)) == token:
            return redirect(url_for('hospital.hospital-approve-appointments', app_id = ap_id))
        else:
            return render_template('hospital/authentication.html',ap_id=ap_id, error_msg = 'Invalid Token')

@hospital.route('/hospital-approve-appointments-list/<app_id>',methods=['GET'])
def hospital_approve_appointments_list(app_id):
    if '_id' in session :
        query = {
        '_id': ObjectId(app_id),     
        }
        update_data = {
            '$set': {'status': 'confirmed'} 
        }
        appointments.update_one(query, update_data)
        appointments_data = appointments.find({'hospital_id': ObjectId(session['_id'])})
        return redirect(url_for('hospital.view-appointments', message = 'Success') )

@hospital.route('/hospital-get-doctors',methods=['GET'])
def hospital_get_doctors():
    if '_id' in session:
        doctors_data = doctors.find({'hospitalId': ObjectId(session['_id'])})
        doctors_data= list(doctors_data)
        return render_template('hospital/doctors-list.html',doctors_data=doctors_data)
    
@hospital.route('/hospital-get-patients',methods=['GET','POST'])
def hospital_get_patients():
    if '_id' in session:
        doc_details = doctors.find({'hospitalId': ObjectId(session['_id'])})
        doc_details = list(doc_details)
        res=[]
        for i in doc_details:
            doctor_id = i['_id']
            
            # Find appointments for the current doctor
            appointments_data = list(appointments.find({'doctor_id': doctor_id}))
            if appointments_data:
                user_id = appointments_data[0]['user_id']
                
                # Find user details based on user_id from the appointments data
                user_details = list(users.find({'_id': user_id}, {'name': 1, 'aadharnumber': 1, '_id': 1}))
                
                if user_details:
                    # Merge user details into appointments_data
                    appointments_data[0].update(user_details[0])
                    appointments_data[0]['doctor_details']=i
                    
                    # Append combined data to the result list
                    res.append(appointments_data)
        print(res)
        
        return render_template('hospital/patients-list.html',user_details=res)

@hospital.route('/view-appointments/',methods=['GET'])
def view_appointments():
    if '_id' in session:
        if request.args.get('message'):
            message = request.args.get('message')
        hospital_details = hospitals.find_one({'_id': ObjectId(session['_id'])})    
        doc_details = doctors.find({'hospitalId': ObjectId(session['_id']) , 'availability': 1})
        doc_details = list(doc_details)
        res=[]
        for i in doc_details:
            doctor_id = i['_id']
            # Find appointments for the current doctor
            appointments_data = list(appointments.find({'doctor_id': doctor_id , 'appointment_date' : datetime.now().strftime("%Y-%m-%d") , 'status' : 'booked'}))
            patients_count = len(list(appointments.find({'doctor_id': doctor_id })))
            if appointments_data:
                user_id = appointments_data[0]['user_id']
                
                # Find user details based on user_id from the appointments data
                user_details = list(users.find({'_id': user_id}, {'name': 1, 'aadharnumber': 1, '_id': 1}))
                
                if user_details:
                    # Merge user details into appointments_data
                    appointments_data[0]['user_details'] =user_details[0]
                    appointments_data[0]['doctor_details']=i
                    
                    # Append combined data to the result list
                    res.append(appointments_data)
        print(res)
        if request.args.get('message') != None:
            return render_template('hospital/appointments.html',hospital_details=hospital_details , appointments_data = res , appointments_count=len(appointments_data) , doctor_count =len(doc_details) , patients_count = patients_count , message = message)   
        else:
            return render_template('hospital/appointments.html',hospital_details=hospital_details , appointments_data = res , appointments_count=len(appointments_data) , doctor_count =len(doc_details) , patients_count = patients_count )  



@hospital.route('/emergency-patient-details', methods=['GET' ,'POST'])
def emergency_patient_details():
    if '_id' in session:
        return render_template('hospital/emergency_patient_details.html',user_details=None)
    
@hospital.route('/search-emergency-patient-details/', methods=['GET' ,'POST'])
def search_emergency_patient_details():
    if '_id' in session :
        if request.method == 'POST':
            user_id = request.form.get('user_id')
            user_details = users.find_one({'aadharnumber': user_id})
            for i,j in user_details['emergency_profile'].items():
                if j== 1:
                    user_details['emergency_profile'][i] = user_details[i]
            if user_details:
                return render_template('hospital/emergency_patient_details.html',user_details=user_details)
            else:
                return render_template('hospital/emergency_patient_details.html',user_details=None)






















@hospital.route('/hospitallogout')
def hospitallogout():
    session.clear()
    return redirect(url_for('hospital.hospital_login')) 


