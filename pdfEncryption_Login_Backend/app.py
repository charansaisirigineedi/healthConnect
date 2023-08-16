import base64
import datetime
import hashlib
import io
import json
import os
import PyPDF2
import bcrypt
from PyPDF2.generic import PdfObject
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient 
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from API_Keys import uri
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature


app = Flask(__name__)
app.secret_key = 'somesecretkey' 

load_dotenv()

client = MongoClient(uri, server_api=ServerApi('1'))

try: 
    client.admin.command('ping')
    print("Connected to MongoDB!")
except Exception as e:
    print(e)

db = client['healthConnectdb']
users = db['users']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])  
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = users.find_one({'username': username})
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['username'] = username
            return render_template('dashboard.html', user = username)
        else:
            return 'Invalid username or password'
            
    return render_template('login.html')

@app.route('/upload')
def upload():
   return render_template('upload.html')

@app.route('/sign', methods=['POST'])  
def sign_pdf():
    report_type = request.form['reportType']

    # Get PDF bytes
    pdf_file = request.files['pdf']
    pdf_bytes = pdf_file.read()

    # Get username
    username = session['username']

    # Lookup private key
    data = users.find_one({'username':username},{'private_key':1})
    private_key_str = data['private_key']
    private_key_bytes = private_key_str.encode('utf-8')

    # Decode private key
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)

    # Hash PDF contents
    pdf_digest = hashlib.sha256(pdf_bytes).digest()

    # Sign hashed PDF
    pdf_signature = private_key.sign(
        pdf_digest,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    pdf_signature_b64 = base64.b64encode(pdf_signature).decode('utf-8')

    # Get timestamp
    timestamp = datetime.datetime.utcnow()

    # Assemble metadata
    metadata = {
        'username': username, 
        'report_type': report_type,
        'timestamp': str(timestamp),
        'pdf_signature': pdf_signature_b64
    }

    metadata_json = json.dumps(metadata)

    # Hash and sign JSON metadata
    metadata_digest = hashlib.sha256(metadata_json.encode('utf-8')).digest()  
    metadata_signature = private_key.sign(
      metadata_digest,
      padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH
      ),
      hashes.SHA256()
    )

    pdf = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    pdf_writer = PyPDF2.PdfWriter()

    pdf_metadata = {
    "/HashedMetadataContent": metadata_signature  
    }
    
    pdf_writer.add_metadata(pdf_metadata)

    num_pages = len(pdf.pages)

    for page_num in range(num_pages):
        page = pdf.pages[page_num]
        pdf_writer.add_page(page) 

    filename = f"{username}_{report_type}.pdf"
    # Save signed PDF
    signed_pdf_path = os.path.join('static/patient_reports', filename)

    with open(signed_pdf_path, "wb") as f:
        pdf_writer.write(f)

    signed_pdf = PyPDF2.PdfReader(signed_pdf_path)
    signed_pdf_bytes = signed_pdf.stream.getvalue()
    signed_pdf_hash = hashlib.sha256(signed_pdf_bytes).digest()
    signed_pdf_hash_b64 = base64.b64encode(signed_pdf_hash).decode('utf-8')
    
    existing = signed_pdf.metadata
    existing = dict(existing)
    existing['/HashedContent'] = signed_pdf_hash_b64

    # existing = json.dumps(existing)
    
    pdf_writer = PyPDF2.PdfWriter()
    pdf_writer.add_metadata(existing)

    num_pages = len(pdf.pages)

    for page_num in range(num_pages):
        page = pdf.pages[page_num]
        pdf_writer.add_page(page)

    with open(signed_pdf_path, "wb") as f:
        pdf_writer.write(f)

    # Update database
    report_info = {'reportType': report_type, 'filename': filename, 'metadata': metadata}
    result = users.update_one({'username': username}, {'$push': {'reports': report_info}})

    # Return response
    if result.matched_count == 1 and result.modified_count == 1:
        return redirect(url_for('display_pdf', filename=filename))
    else:
        os.remove(signed_pdf_path)
        flash('Error updating report info')
        return redirect(url_for('upload'))

@app.route('/display_pdf/<filename>')
def display_pdf(filename):
    pdf_url = f'/static/patient_reports/{filename}'
    return render_template('display.html', pdf_url=pdf_url)

@app.route('/validate_form')
def validate_form():
    return render_template('validate.html')

@app.route('/validate', methods=['POST'])
def validate_pdf():
    output = ""
    pdf_file = request.files['pdf']
    filename = pdf_file.filename
    
    pdf = PyPDF2.PdfReader(pdf_file)
    pdf_info = pdf.metadata
    original_hashedcontent = pdf_info['/HashedContent']
    metadata_signature = pdf_info['/HashedMetadataContent']

    pdf.metadata.pop('/HashedContent', None)

    revised_metadata = pdf.metadata
    revised_metadata = dict(revised_metadata)
    del revised_metadata['/HashedContent']
    print(revised_metadata)
    # Re-hash PDF contents
    
    new_pdf_path = 'temp.pdf'
    writer = PyPDF2.PdfWriter()

    num_pages = len(pdf.pages)

    for page_num in range(num_pages):
        page = pdf.pages[page_num]
        writer.add_page(page)
  
    writer.add_metadata(revised_metadata)
    
    with open(new_pdf_path, 'wb') as f:
      writer.write(f)

    new_pdf = PyPDF2.PdfReader(new_pdf_path)
    new_pdf_bytes = new_pdf.stream.getvalue()
    new_pdf_digest = hashlib.sha256(new_pdf_bytes).digest()
    new_hashedcontent = base64.b64encode(new_pdf_digest).decode('utf-8')

    os.remove(new_pdf_path)

    username = session['username']
    data = users.find_one({'username': username},{'public_key': 1,'reports': {'$elemMatch': {'filename': filename  }}})
    public_key_str = data['public_key']
    public_key_bytes = public_key_str.encode('utf-8')

    public_key = serialization.load_pem_public_key(public_key_bytes)
    report_metadata = data['reports'][0]['metadata']

    metadata_json = json.dumps(report_metadata)

    # Hash and sign JSON metadata
    metadata_digest = hashlib.sha256(metadata_json.encode('utf-8')).digest()

    try:
      public_key.verify(
          metadata_signature,
          metadata_digest,
          padding.PSS(
              mgf=padding.MGF1(hashes.SHA256()),
              salt_length=padding.PSS.MAX_LENGTH
          ),
          hashes.SHA256()  
      )
      output = output + "Meta data valid"
    except InvalidSignature:
        output = output + "Meta data invalid"

    if original_hashedcontent == new_hashedcontent:
      output += "Content not tampered"
    else:
      output += "Content tampered"

    print(original_hashedcontent)
    print(new_hashedcontent)

    return output
    
    
@app.route('/viewreports')
def view_reports():
  if 'username' in session:
    user = users.find_one({'username': session['username']})
    if user:
      return render_template('viewreports.html', reports=user['reports'])
  else: 
    return redirect(url_for('login'))


@app.route('/viewkeys')
def view_keys():
  if 'username' in session:
    user = users.find_one({'username': session['username']})
    if user:
      return render_template('keys.html',user=user)
  else:
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():

  if request.method == 'POST':

    # Get form data
    username = request.form.get('username')
    password = request.form.get('password') 
    name = request.form.get('name')
    phone = request.form.get('phone')
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    
    #generating pem
    private_key_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,format=serialization.PrivateFormat.PKCS8,encryption_algorithm=serialization.NoEncryption())
    public_key_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo)
    
    # Validate required fields
    if not username or not password or not name or not phone:
      return jsonify({'message': 'All fields are required'}), 400

    # Check duplicate usernames
    existing_user = users.find_one({'username': username})

    if existing_user:
      return jsonify({'message': 'Username already exists'}), 400
   
    # Hash password 
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert user
    user = {
      'username': username,
      'password': hashed_password,
      'name': name,
      'phone': phone,
      'private_key': private_key_pem.decode('utf-8'),
      'public_key': public_key_pem.decode('utf-8'),
      'reports': []
    }


    try:
      result = users.insert_one(user)
      
      if result.inserted_id:
        return redirect(url_for('login'))
      else:
        return jsonify({'message': 'User creation failed'}), 500

    except Exception as e:
      print(e)
      return jsonify({'message': 'Unknown error'}), 500

  else:
    # GET request - show signup form
    return render_template('signup.html')
  
@app.route('/logout', methods=['POST'])
def logout():

  # Remove the username from the session
  session.pop('username', None)  

  # Clear the entire session
  session.clear()

  # Delete the session cookie
  session.permanent = True
  app.permanent_session_lifetime = datetime.timedelta(minutes=1)

  return redirect(url_for('index'))

if __name__ == '__main__':
    app.run()