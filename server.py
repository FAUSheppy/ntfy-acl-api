from flask import Flask, request, jsonify
import subprocess
import os
import sys
import time

app = Flask("NTFY HTTP API")

SERVER_CONFIG_FILE = "/etc/ntfy/server.yml"

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

    if flask.request.method == "PUT":

        # create user #
        cp = subprocess.run(['ntfy', 'user', "add", user], env={"NTFY_PASSWORD" : password})
        if cp.return_code == 1:
            print("User {} already exists - ignoring..".format(user))

        # set topic access #
        subprocess.run(['ntfy', 'access', user, topic, 'r'], check=True)

    if flask.request.method == "DELETE":
        subprocess.run(['ntfy', 'access', "--reset", user, topic], check=True, env={"NTFY_PASSWORD" : password})

    return jsonify({'message': 'Command executed successfully'}), 200

def create_app():

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
            break
        elif ret.returncode != 0:
            print("WARNING:", ret.stderr.decode(), ret.stdout.decode(), file=sys.stderr)
            time.sleep(5)
        else:
            break

if __name__ == '__main__':
    app.run(debug=True)
