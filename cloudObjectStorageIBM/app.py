import base64
import os
from bson import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient 
from pymongo.server_api import ServerApi
import ibm_boto3
from ibm_botocore.client import Config, ClientError

from secretKeys import ACCESS_KEY_ID, API_KEY_ID, ENDPOINT, INSTANCE_CRN, SECRET_ACCESS_KEY

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

COS_ENDPOINT = ENDPOINT
COS_API_KEY_ID = API_KEY_ID
COS_INSTANCE_CRN = INSTANCE_CRN


cos = ibm_boto3.client("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

cosReader = ibm_boto3.client("s3",
            aws_access_key_id=ACCESS_KEY_ID,
            aws_secret_access_key=SECRET_ACCESS_KEY,
            endpoint_url=COS_ENDPOINT
)

@app.route('/')
def index():
    return "Hello Word!!!"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']        
        result = users.find_one({"aadharnumber": username},{})
        if result:
            session['ID'] = str(result['_id'])
            session['NAME'] = result['name']
            return redirect(url_for('dashboard'))                        
        else:
            return "Invalid"
    else:
        return render_template('index.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'ID' in session:
        return render_template('dashboard.html')
    else:
        return redirect(url_for('login'))
    

@app.route('/upload', methods=['POST'])
def upload_file():
    report_type = request.form['reportType']
    uploaded_file = request.files['file']

    if uploaded_file:
        user_name = session['ID']
        filename = f"{user_name}_{report_type}.pdf"

        # Save the uploaded file in the current folder
        uploaded_file.save(filename)

        try:
            # Upload the file to COS
            cos.upload_file(Filename=filename, Bucket='healthconnectibm', Key=filename)
        except Exception as e:
            return f"Error uploading to COS: {e}"
        else:
            # Remove the uploaded file after successful upload
            os.remove(filename)

            report_info = {'reportType': report_type, 'filename': filename}
            query = {"_id": ObjectId(session['ID'])}
            update = {"$push": {"pdfReports": report_info}}
            users.update_one(query, update)

            return "File uploaded and removed from server."
    else:
        return "File upload failed."
    
@app.route('/viewreports')
def view_reports():
  if 'ID' in session:
    user = users.find_one({'_id': ObjectId(session['ID'])})
    if user:
      return render_template('viewreports.html', reports=user['pdfReports'])
  else: 
    return redirect(url_for('login'))
  
@app.route('/display_pdf/<filename>')
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
    return render_template('display.html', pdfUrl = signedUrl)

if __name__ == '__main__':
    app.run(debug=True)
