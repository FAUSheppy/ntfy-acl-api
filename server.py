from flask import Flask, request, jsonify
import flask
import subprocess
import os
import token
import sys
import time
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, or_, and_, asc, desc

app = Flask("NTFY HTTP API")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLITE_LOCATION") or "sqlite:///sqlite.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

SERVER_CONFIG_FILE = "/etc/ntfy/server.yml"

def _alphanumeric_topic_name(length=20):
    '''Generate an alphanumeric topic name which starts with a letter'''

    both = string.ascii_letters + string.digits
    random_string = random.choice(string.ascii_letters)
    random_string += ''.join(random.choices(both, k=length))
    return random_string

class UserTopic(db.Model):

    __tablename__ = 'topics'

    user = Column(String, primary_key=True)
    topic = Column(String)

@app.route('/topic', methods=['GET', 'PUT', 'DELETE'])
def topic_route():
    '''Manage and query hidden topics instead of password ACLs'''

    # Get the token from the environment variable
    token = os.getenv('ACCESS_TOKEN')

    # Check if the token is provided in the request
    provided_token = request.args.get('token')
    if not provided_token or provided_token != token:
        return jsonify({'error': 'Invalid token'}), 401

    user = request.args.get("user")

    if request.method == 'GET':
        topic = db.session.query(UserTopic).filter_by(user=user).first()
        if topic:
            return jsonify({'user': topic.user, 'topic': topic.topic})
        else:
            return jsonify({'message': 'Topic not found'}), 404

    elif request.method == 'PUT':

        topic = db.session.query(UserTopic).filter_by(user=user).first()

        if topic:
            return jsonify({'message': 'Topic already exists'}), 409
        else:
            topic = db.session.query(UserTopic).filter(user=user, topic=_alphanumeric_topic_name())
            subprocess.run(['ntfy', 'access', "everyone", topic, "ro"], check=True)
            db.session.add(topic)

        db.session.commit()
        return jsonify({'user': topic.user, 'topic': topic.topic})

    elif request.method == 'DELETE':
        topic = db.session.query(UserTopic).filter_by(user=user).first()
        if topic:
            db.session.delete(topic)
            subprocess.run(['ntfy', 'access', "--reset", "everyone", topic], check=True)
            db.session.commit()
            return jsonify({'message': 'Topic deleted successfully'})
        else:
            return jsonify({'message': 'Topic not found'}), 404


@app.route('/access-and-user', methods=['PUT', "DELETE"])
def access_and_user():
    '''Add or delete access and user to the ACL'''

    # Get the token from the environment variable
    token = os.getenv('ACCESS_TOKEN')

    # Check if the token is provided in the request
    provided_token = request.args.get('token')
    if not provided_token or provided_token != token:
        return jsonify({'error': 'Invalid token'}), 401

    # Get user and topic from URL arguments
    user = request.args.get('user')
    topic = request.args.get('topic')

    # Check if user and topic are provided
    if not user or not topic:
        return jsonify({'error': 'User and topic are required'}), 400

    password = flask.request.args.get("password")
    if not password:
        return jsonify({'error': 'Missing password for user'}), 400

    if flask.request.method == "PUT":

        # create user #
        cp = subprocess.run(['ntfy', 'user', "add", user], env={"NTFY_PASSWORD" : password})
        if cp.returncode == 1:
            print("User {} already exists - ignoring..".format(user), file=sys.stderr)

        # set topic access #
        subprocess.run(['ntfy', 'access', user, topic, 'ro'], check=True)

    if flask.request.method == "DELETE":
        subprocess.run(['ntfy', 'access', "--reset", user, topic], check=True)
        subprocess.run(['ntfy', 'user', "remove", user], check=True)

    return jsonify({'message': 'Command executed successfully'}), 200

def create_app():

    db.create_all()

    app.config["ACCESS_TOKEN"] = os.getenv('ACCESS_TOKEN')
    if not app.config["ACCESS_TOKEN"]:
        print("Missing ACCESS_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    # need to write this to /etc/ntfy/server.yaml as "auth-file" #
    auth_file = os.getenv("NTFY_AUTH_FILE")
    if not auth_file:
        print("Missing NTFY_AUTH_FILE environment variable", file=sys.stderr)
        sys.exit(1)

    # check if already set / create file #
    auth_file_already_set = False
    if os.path.isfile(SERVER_CONFIG_FILE):
        with open(SERVER_CONFIG_FILE) as f:
            for l in f:
                if l.strip().startswith("#"):
                    continue
                if "auth-file" in l and l.split("auth-file")[1].strip():
                        auth_file_already_set = True
                        break
    else:
        os.makedirs("/etc/ntfy", exist_ok=True)

    # if not set, add it at the end #
    with open(SERVER_CONFIG_FILE, "a") as f:
        f.write("\nauth-file: {}\n".format(auth_file))

    passenv = {"NTFY_PASSWORD" : app.config["ACCESS_TOKEN"]}

    # try a few times #
    for i in range(0, 5):

        ret = subprocess.run(['ntfy', 'user', "add", "--role=admin", "dispatcher"], env=passenv,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if ret.returncode == 1 and "auth-file does not exist" in ret.stderr.decode():
            print("Auth file missing, waiting for server to create it...", file=sys.stderr)
            time.sleep(5)
        elif ret.returncode == 1 and "already exists" in ret.stderr.decode():
            print("Admin user already exists - continue...", file=sys.stderr)
            return
        elif ret.returncode != 0:
            print("WARNING:", ret.stderr.decode(), ret.stdout.decode(), file=sys.stderr)
            time.sleep(5)
        else:
            return

    # -- something went wrong -- #
    print("Failed to start - see output. Probably ntfy server didn't start or mounts are wrong", file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    app.run(debug=True)
