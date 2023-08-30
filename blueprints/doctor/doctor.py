import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, redirect, render_template, session, url_for, request
from blueprints.database_connection import doctors, appointments, users, medicines
from blueprints.ibm_connection import cosReader 
from blueprints.redis_connection import r

doctor = Blueprint("doctor",__name__,template_folder="templates")

@doctor.route('/doctorsignup',methods=['POST','GET'])
def doctorsignup():
    if request.method == 'POST':
        # Get form data
        dname = request.form.get('d-name')
        dpassword = request.form.get('d-password') 
        demail = request.form.get('d-email')
        
        # Validate required fields
        if not dname or not demail or not dpassword:
            return jsonify({'message': 'All fields are required'}), 400

        # Check duplicate usernames
        existing_user = doctors.find_one({'email':demail })

        if existing_user:
            return jsonify({'message': 'Email already exists'}), 400

        # Insert user
        user = {
        'name': dname,
        'email': demail,
        'password': dpassword,

        }
        
        try:
            result = doctors.insert_one(user)
            session['doctor_id'] = str(result.inserted_id)
        
            if result.inserted_id:
                doctor_id = session.get('doctor_id') 
                return redirect(url_for('doctor.doctordashboard', doctor_id=doctor_id))
            else:
                return jsonify({'message': 'User creation failed'}), 500

        except Exception as e:
            print(e)
            return jsonify({'message': 'Unknown error'}), 500
    else:
        # GET request - show signup form
        return render_template('doctor/authentication-register2.html')

@doctor.route('/doctorlogin',methods=['POST','GET'])
def doctorlogin():
    if request.method == 'POST':
        demail = request.form['d-email']
        dpassword = request.form['d-password']
        doctor = doctors.find_one({'username': demail,'password':dpassword})
        if doctor:                       
            session['email'] = demail
            session['doctor_id'] = str(doctor['_id'])
            return redirect(url_for('doctor.doctordashboard'))
        else:
            return 'Invalid username or password'
            
    return render_template('doctor/authentication-login2.html')

@doctor.route('/doctordashboard')
def doctordashboard():
     doctor_id = session.get('doctor_id')
     if doctor_id:
        doctor_data = doctors.find_one({'_id':ObjectId(doctor_id)})
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id)})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})
            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }
            appointments_with_users.append(appointment_with_user)
        return render_template('doctor/doctor-dashboard.html', doctor_data=doctor_data, appointments_with_users=appointments_with_users)
     else:
         return 'Unauthorized'
     
@doctor.route('/update_doctor_availability', methods=['POST'])
def update_doctor_availability():
    data = request.get_json()
    doctor_id = data.get('doctorId')
    availability = data.get('availability')

    if doctor_id and availability is not None:
        # Convert the doctor_id to ObjectId
        doctor_id_obj = ObjectId(doctor_id)

        # Update the doctor's availability in the doctors collection
        doctors.update_one({"_id": doctor_id_obj}, {"$set": {"availability": availability}})

        return jsonify({"message": "Doctor availability updated successfully"}), 200
    else:
        return jsonify({"message": "Invalid data provided"}), 400

@doctor.route('/doctor_appointments')
def doctor_appointments():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        current_date= datetime.datetime.now().date()
        date1 = str(current_date.strftime('%Y-%m-%d'))
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id),"appointment_date":date1,'$or':[{'status':'booked'},{'status':'pending'}]})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})

            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }
            appointments_with_users.append(appointment_with_user)
        # appointment_ids = [str(appointment_with_user['appointment']['_id']) for appointment_with_user in appointments_with_users]
        # session['appointment_ids'] = appointment_ids
        return render_template('doctor/doctor-appointments.html', appointments_with_users=appointments_with_users)
    else:
        return 'Unauthorized'   
@doctor.route('/completed_doctor_appointments')
def completed_doctor_appointments():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        current_date=datetime.datetime.now().date()
        date1 = str(current_date.strftime('%Y-%m-%d'))
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id),"appointment_date":date1,"status":'completed'})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})

            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }
            appointments_with_users.append(appointment_with_user)
        
        return render_template('doctor/completed_doctor-appointments.html', appointments_with_users=appointments_with_users)
    else:
        return 'Unauthorized'  
@doctor.route('/lab_doctor_appointments')
def lab_doctor_appointments():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        current_date=datetime.datetime.now().date()
        date1 = str(current_date.strftime('%Y-%m-%d'))
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id),"appointment_date":date1,"status":'tests_required'})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})

            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }
            appointments_with_users.append(appointment_with_user)
        
        return render_template('doctor/lab_doctor-appointments.html', appointments_with_users=appointments_with_users)
    else:
        return 'Unauthorized' 
    
@doctor.route('/patientreports/<user_id>/<appointment_id>')
def patientreports(user_id,appointment_id):
    user_data = users.find_one({"_id": ObjectId(user_id)})
    appointments.update_one({'_id':ObjectId(appointment_id)},{'$set':{'status':"pending"}})
    session['APPOINTMENT_ID']=appointment_id
    session['USER_ID']=user_id
    if user_data:
        pdf_reports = user_data.get('pdfReports', [])
        # doctor_id = session.get('doctor_id')
        # if doctor_id:
        #     doctor_data = doctors.find_one({"_id": ObjectId(doctor_id)})
        return render_template('doctor/patient-records-list.html',user_id=user_id,appointment_id=appointment_id, user_data=user_data,pdf_reports=pdf_reports)
    else:
        return "User not found"

@doctor.route('/lab_tests_required',methods=['POST'])
def lab_tests_required():
    appointment_id = session['APPOINTMENT_ID']
    user_id = session['USER_ID']
    if appointment_id:
        plist=list(request.form['test'].split(','))
        updated = appointments.update_one({'_id':ObjectId(appointment_id)},{'$push':{'lab_tests':{ '$each': plist }},'$set': {'status': 'tests_required'}})
        if updated:
            return redirect(url_for('doctor.doctordashboard'))

@doctor.route('/doctor_display_pdf/<filename>',methods=['GET'])
def doctor_display_pdf(filename):
    doctor_id = session.get('doctor_id')
    if doctor_id:
        appointment_id = session['APPOINTMENT_ID']
        appointment = appointments.find_one({"_id": ObjectId(appointment_id)})
        user_id=appointment['user_id']
        pdf_reports = users.find_one({"_id": ObjectId(user_id)},{'pdfReports':1,'_id':0})
        pdf_reports = pdf_reports['pdfReports']
        access_token = appointment.get("accessToken")
        getstatus = appointment.get("status")
        if not r.get(appointment_id) and getstatus == "pending":
            r.set(appointment_id, access_token, ex=60)
        if r.get(appointment_id):
            print("hello")
        else:
            return 'Acess Denied'
        bucket_name = 'healthconnectibm'
        key_name = filename
        http_method = 'get_object'
        expiration = 600
        try:
            signedUrl = cosReader.generate_presigned_url(http_method, Params={'Bucket': bucket_name, 'Key': key_name}, ExpiresIn=expiration)
            return render_template('doctor/patient-pdfreports.html', pdfUrl=signedUrl,filename=filename,pdfreports=pdf_reports)
        except Exception as e:
            print(e)
            return "Cannot load data"
    return "No valid appointment IDs found"

@doctor.route('/tabletsprescription',methods=['POST','GET'])
def tabletsprescription():
    if request.method=='POST':
        reports_review = request.form.get('report_reviews')
        medicine_list = list(medicines.find())
        prescriptions_list=[]
        prescriptions_list = list(appointments.find({'_id':ObjectId(session['APPOINTMENT_ID'])},{'prescription':1,'_id':0}))
        return render_template('doctor/tablets-prescription.html',medicines=medicine_list,prescriptions_list=prescriptions_list)
    else:
        medicine_list = list(medicines.find())
        prescriptions_list=[]
        prescriptions_list = list(appointments.find({'_id':ObjectId(session['APPOINTMENT_ID'])},{'prescription':1,'_id':0}))
        return render_template('doctor/tablets-prescription.html',medicines=medicine_list,prescriptions_list=prescriptions_list)

    
@doctor.route('/prescriptions_pdf',methods=['POST','GET'])
def prescriptions_pdf():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        if request.method == 'POST':
            data = request.json
            name,mname = data.get('charge').split(',')
            days = data.get('days')
            morning = data.get('mor')
            afternoon = data.get('aft')
            evening = data.get('evn')
            plist={'medicine_name':name,'medicine_mname':mname,'course_days':days,'morning':morning,'afternoon':afternoon,'evening':evening}
            appointments.update_one({'_id':ObjectId(session['APPOINTMENT_ID'])},{'$push':{'prescription':plist}})
            return jsonify(plist)
        

        
@doctor.route('/delete_medication/<medicine_names>',methods=['GET','POST'])
def delete_medication(medicine_names):
    delete= appointments.update_one({'_id':ObjectId(session['APPOINTMENT_ID'])},{'$pull': {'prescription': {'medicine_name': medicine_names}}})
    if delete:
        return redirect(url_for('doctor.tabletsprescription'))
    
@doctor.route('/prescription_submitted')
def prescription_submitted():
    user_id = session.get('USER_ID')
    appointment_id=session['APPOINTMENT_ID']
    return redirect(url_for('doctor.patientreports',user_id=user_id,appointment_id=appointment_id))

@doctor.route('/doctor_reviews/<appointment_id>/<user_id>')
def doctor_reviews(appointment_id,user_id):
    doctor_id = session.get('doctor_id')
    plist=appointments.find({'_id':ObjectId(appointment_id)},{'prescription':1})
    return render_template('doctor/app-invoice.html',appointment_id=appointment_id,user_id=user_id,plist=plist)

@doctor.route('/prescription')
def prescription():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        return  render_template('doctor/app-invoice.html')


@doctor.route('/doctorappointments')
def doctorappointments():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id)})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})

            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }
            appointments_with_users.append(appointment_with_user)
        
        appointment_ids = [str(appointment_with_user['appointment']['_id']) for appointment_with_user in appointments_with_users]
        session['appointment_ids'] = appointment_ids
        return render_template('doctor/doctor-appointments.html', appointments_with_users=appointments_with_users)
    else:
        return 'Unauthorized'

@doctor.route('/doctorpatients')
def doctorpatients():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        doctor_data = doctors.find_one({'_id':ObjectId(doctor_id)})
        doctor_appointments = appointments.find({"doctor_id": ObjectId(doctor_id)})
        appointments_with_users = []
        for appointment in doctor_appointments:
            user_id = appointment.get("user_id")
            user_data = users.find_one({"_id": ObjectId(user_id)})

            # Include the user data along with appointment data
            appointment_with_user = {
                "appointment": appointment,
                "user": user_data
            }

            appointments_with_users.append(appointment_with_user)
        return render_template('doctor/doctor-patients.html', doctor_data=doctor_data, appointments_with_users=appointments_with_users)
    else:
        return 'Unauthorized'

    
@doctor.route('/doctorprofile' , methods=['POST','GET'])
def doctorprofile():
    doctor_id = session.get('doctor_id')
    if doctor_id:
        doctor_data = doctors.find_one({'_id':ObjectId(doctor_id)})
        if request.method == 'POST':
            experience = request.form.get('experience')
            new_password = request.form.get('new_password')

            # Update the doctor's information in the database
            doctors.update_one(
                {"_id": ObjectId(doctor_id)},
                {"$set": {"experience": experience, "password": new_password}}
            )

            # Optionally, update the doctor_data dictionary with the new values
            doctor_data['experience'] = experience
            doctor_data['password'] = new_password

            return render_template('doctor/doctor-profile.html', doctor_data=doctor_data)
        
        return render_template('doctor/doctor-profile.html', doctor_data=doctor_data)
    
@doctor.route('/doctorlogout')
def doctorlogout():
    session.pop('doctor_id', None)
    return redirect(url_for('doctor.doctorlogin'))