from flask import Flask, redirect, render_template, request, session, url_for
from getTokens import addEvent
from datetime import datetime
from database import users

app = Flask(__name__)

app.secret_key = 'somesecretkey'


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']        
        result = users.find_one({"aadharnumber": username},{})
        if result:
            session['ID'] = str(result['_id'])
            return redirect(url_for('dashboard'))                        
        else:
            return "Invalid"
    else:
        return render_template('index.html')
    
@app.route('/dashboard', methods=['GET', 'POST'])  
def dashboard():

    if request.method == 'POST':
        summary = request.form['summary']
        location = request.form['location']
        description = request.form['description']
        
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')

        end_date = request.form.get('end_date')
        end_time = request.form.get('end_time')

        start_datetime = datetime.strptime(start_date + " " + start_time, "%Y-%m-%d %H:%M").isoformat() + "+05:30"
        end_datetime = datetime.strptime(end_date + " " + end_time, "%Y-%m-%d %H:%M").isoformat() + "+05:30"

        print(start_datetime, end_datetime)

        
        event = {
            "summary": summary,
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
                {"method": "email", "minutes":5},
                {"method": "popup", "minutes": 10}
            ]
            },
            "visibility":"public",
            "sendNotifications": True,
            "sendUpdates": "all"
        }
        
        addEvent(session['ID'],0,event)
        return redirect('/')

    else:
        return render_template('dashboard.html')
    
@app.route('/fit_data')
def fit_data():
    value = addEvent(session['ID'],2,date='2023-08-27')
    return value

if __name__ == '__main__':
    app.run(debug=True)