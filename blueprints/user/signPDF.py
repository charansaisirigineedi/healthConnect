import base64
import datetime
import io
import json
import os
import PyPDF2
import hashlib
from bson import ObjectId
from blueprints.database_connection import users
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding



def sign(pdf_bytes,username,report_type):
    data = users.find_one({'_id':ObjectId(username)},{'private_key':1})
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
    signed_pdf_path = os.path.join('static/temporary_reports', filename)

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
    
    return [signed_pdf_path, filename]
