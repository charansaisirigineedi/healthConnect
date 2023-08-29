from flask import Flask
from blueprints.doctor.doctor import doctor
from blueprints.lab.lab import lab
from blueprints.user.user import user

app = Flask(__name__)
app.secret_key = 'YOU CAN BE ANYTHING'
app.register_blueprint(user)
app.register_blueprint(doctor)
app.register_blueprint(lab)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port= 5000)