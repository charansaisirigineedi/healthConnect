from datetime import datetime
import os
import bcrypt
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from bson import ObjectId
from blueprints.database_connection import users, appointments, labs
from blueprints.ibm_connection import cos
from blueprints.signPDF import sign
from blueprints.blockChainLogging import blockChain


lab = Blueprint("lab", __name__, template_folder="templates")

@lab.before_request
def check_session():
    if request.endpoint not in ['lab.lab_register', 'lab.lab_login'] and '_id' not in session:
        return redirect(url_for('lab.lab_login'))

@lab.route('/lab_register', methods=['GET', 'POST'])
def lab_register():
    if request.method =="POST":
        labname = request.form.get('labname')
        phone = request.form.get('mobile')
        password = request.form.get('labpassword')
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        lab = {
        'labname': labname,
        'password': hashed_password,
        'phone': phone
        }
        try:
            result = labs.insert_one(lab)
        
            if result.inserted_id:
                return redirect(url_for('lab.lab_login'))
            else:
                return render_template('lab/lab-login.html', message='User not created')

        except Exception as e:
            print(e)
            return jsonify({'message': 'Unknown error'}), 500
    else:
        # GET request - show signup form
        return render_template('lab/lab-register.html')    
    

@lab.route('/lab_login', methods=['GET', 'POST'])
def lab_login():
    session.clear()
    if request.method == "POST":
        lid= request.form.get('username')
        password = request.form.get('password')
        lab = labs.find_one({'labname': lid})
        if lab and bcrypt.checkpw(password.encode('utf-8'), lab['password']):
            session.permanent = True 
            session['_id'] = str(lab['_id'])
            session['username']=lab['labname']
            message = "Lab ID: " + str(session['_id']) + " logged into his account"
            blockChain(message)
            return redirect(url_for('lab.lab_dashboard'))
        else:
            return render_template('lab/lab-login.html', message='Incorrect aadharnumber/password combination')
            
    return render_template('lab/lab-login.html')

@lab.route('/lab-dashboard',methods=['GET'])
def lab_dashboard():
    if  '_id' in session:
        lab_id = labs.find_one({'_id':ObjectId(session['_id'])})
        return render_template('lab/lab-dashboard.html',lab_id=lab_id)

@lab.route('/search-lab-appointments',methods=['POST','GET'])
def search_lab_appointments():
    if '_id' in session:
        user_id = request.form.get('user_id')
        app_details , user_details= get_patient_lab_appointments(user_id)
        return render_template('lab/lab-dashboard.html',app_details=app_details , user_details=user_details)

@lab.route('/view-lab-app-details/<user_id>',methods=['GET'])
def view_lab_app_details(user_id):
    if '_id' in session:
        app_details , user_details = get_patient_lab_appointments(user_id) 
        print(app_details)
        return render_template('lab/view-lab-app-details.html',app_details=app_details , user_details=user_details)


@lab.route('/get-patient-lab-appointments',methods=['GET'])
def get_patient_lab_appointments(user_id):
    user_details = users.find_one({'aadharnumber':user_id})
    query = {'$and': [{'status': 'tests_required'}, {'user_id': ObjectId(user_details['_id'])}]}
    projection = {'_id': 1, 'lab_tests': 1 , 'user_id' :1 , 'lab_reports' : 1}
    res =  appointments.find(query, projection)
    res=list(res)
    if res is None:
        return {'message':'No appointments found'}
    return res , user_details

@lab.route('/upload-lab-reports/<ap_id>/<user_id>', methods=['POST'])
def upload_lab_reports(ap_id , user_id):
    report_type = request.form.get('report_type')
    uploaded_file = request.files['file']
    pdf_bytes = uploaded_file.read()
    app_details , user_details = get_patient_lab_appointments(user_id)
    location, filename = sign(pdf_bytes=pdf_bytes, username=str(user_details['_id']),report_type=report_type)
    if uploaded_file:
        try:
            cos.upload_file(Filename=location, Bucket='healthconnectibm', Key=filename)
        except Exception as e:
            os.remove(location)
            return f"Error uploading to COS: {e}"
        else:
            os.remove(location)
            message = "Lab ID: " + str(session['_id']) + " (Appointment ID: " + ap_id + ") uploaded file " + filename + " of user(ID: " + user_id + ")"
            blockChain(message)
            report_info = {'reportType': report_type, 'filename': filename , 'timestamp': datetime.now()}
            query = {"_id": ObjectId(app_details[0]['_id'])}
            update = {"$push": {"lab_reports": report_info}}
            appointments.update_one(query, update)

            query = {"_id": ObjectId(user_details['_id'])}
            update = {"$push": {"pdfReports": report_info}}
            users.update_one(query, update)
            print(app_details)
            app_details , user_details = get_patient_lab_appointments(user_id)

            # appointments.update_one({'_id':ObjectId(ap_id)},{'$set':{'status':'booked'}})
            return render_template('lab/view-lab-app-details.html',message ="File uploaded Succesfully !",type="success", user_details = user_details , app_details = app_details)
    else:
        return render_template('user/view-lab-app-details.html',message ="File not uploaded",type="error",user_details = user_details , app_details = app_details)
    
@lab.route('/finish-reports/<ap_id>',methods=['GET'])
def finish_reports(ap_id):
    if '_id' in session:
        query = {'_id': ObjectId(ap_id)}
        update_data = {'$set': {'status': 'pending'}}
        appointments.update_one(query, update_data)
        return redirect(url_for('lab.lab_dashboard'))

@lab.route('/lablogout')
def lablogout():
    session.clear()
    return redirect(url_for('lab.lab_login'))