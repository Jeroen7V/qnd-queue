from flask import Flask, abort, request, jsonify, g, url_for, redirect

from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context

from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired)

import os
import sys
import traceback
import threading
import json
import datetime
import time

# initialization
app = Flask(__name__)
management = Flask(__name__)

# extensions: db + auth
db = SQLAlchemy(app)
auth = HTTPBasicAuth()

class User(db.Model):
    """
    Basic user model
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    queue = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(64))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token
        user = User.query.get(data['id'])
        return user

class Message(db.Model):
    """
    Queue message
    """
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    queue = db.Column(db.String(32), index=True)
    username = db.Column(db.String(32))
    message = db.Column(db.String)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Style:
    """
    Style class, contains all HTML formatting
    """

    STYLE_MQS_START = '<h2>Message queue: $QUEUE$</h2><table class="gridtable"><tr><th>id</th><th>actions</th><th>created</th><th>message</th></tr>'
    STYLE_MQS_ROW = '<tr><td>$ID$</td><td><a onclick="msgbox(\'Do you want to delete message id: $ID$?\',\'/process?action=delete_msg&id=$ID$&queue=$QUEUE$\')"><img class="delete" /></a></td><td>$DATE$</td><td class="break">$MSG$</td></tr>'
    STYLE_MQS_END = '</table>'

    STYLE_MQS_BACK_BUTTON = '<p><button type="button" onclick="window.location.href=\'/index\'">Back</button></p>'
    STYLE_MQS_INPUTBOX = '<h2>Input Data</h2><p><textarea id="content" cols="50" rows="6"></textarea></p><p><input type="hidden" id="queue" value="$QUEUE$"><button type="button" onclick="post()">Post</button></p>'

    STYLE_ADMIN_HEADER = '<table class="gridtable"><tr><th>id</th><th>username</th><th>actions</th></tr>'
    STYLE_ADMIN_FOOTER = '</table>'

    STYLE_MESSAGES_HEADER = '<table class="gridtable"><tr><th>id</th><th>username</th><th>queue</th><th>messages</th><th>actions</th></tr>'
    STYLE_MESSAGES_FOOTER = '</table>'

    BASIC_RETURN = """
    <!DOCTYPE html>
    <html>
    <head>
    <script>
    window.location.href = '$URL$';
    </script>
    </head>
    <body>
    </body>
    </html>
    """

    BASIC_PAGE = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>$TITLE$</title>
    <style type="text/css">
    table.gridtable {
	    font-family: verdana,arial,sans-serif;
	    font-size:11px;
	    color:#333333;
	    border-width: 1px;
	    border-color: #666666;
	    border-collapse: collapse;
    }
    table.gridtable th {
	    border-width: 1px;
	    padding: 8px;
	    border-style: solid;
	    border-color: #666666;
	    background-color: #dedede;
    }
    table.gridtable td {
	    border-width: 1px;
	    padding: 8px;
	    border-style: solid;
	    border-color: #666666;
	    background-color: #ffffff;
    }
    .break {
        word-break: break-all;
    }
    .edit {
        background: url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAQAAAD8x0bcAAAAW0lEQVR4AcXN3QmAMBAE4YnVWJdakwTxpzZBsIuLS57NGRBx5/WD5d0aNg5aHy0kdfqswzLbS0ezCPSZjfdkJWEiMBAJJaIwEcAjivhMJsKPhBpCDaGGUCAf7AKbbkmNukpEmgAAAABJRU5ErkJggg==');
        no-repeat
        left center;
        padding: 2px 0px 16px 18px;
    }
    .delete {
        background: url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAQAAAD8x0bcAAAAdUlEQVR4AWOgETBi2MdwAAj3AVlYgAPDfyzQAVWRAkMDFqiAblYCwwE0mIBpYQOGZQ24FP2CkPgU7WJQYrgBhEoMe3Erus4gAYaSDDfxWbcBzN6Iz7obxJi0l0EZKA12EwW+S8IIpyRMRVwM3Sjh3Q0UoToAAEi7YGRptLwpAAAAAElFTkSuQmCC');
        no-repeat
        left center;
        padding: 2px 0px 16px 18px;
    }
    .magnify {
        background: url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAQAAAD8x0bcAAAAnklEQVR4AbXKIW4CQRQA0Dcah8CiOMCKij3KOk6A5QQ1IJHAKQgJ3GAkAl1HQtIq1CBgakl+0jX06ecfDM3tHC1NgOjD1dNZVtxNiYauvjRg5OChFcw9NQAGLvaCnbNXKzfBUfZqoQiWihGA5CQLJu4OBiD5VHUiUw8XKwsn1beZRNTauymyzky1lfwp2ao2/W2jWve3tR9jPZKxN/sFG20vy4vNVycAAAAASUVORK5CYII=')
        no-repeat
        left center;
        padding: 2px 0px 16px 18px;
    }

    </style>
    <script>
    function getSelectedText(elementId) {
        var elt = document.getElementById(elementId);

        if (elt.selectedIndex == -1)
            return null;
        try {
            return elt.options[elt.selectedIndex].text;
        }
        catch(err) {
            return elt.value;
        }
    }

    function setSelectedText(elementId, value) {
        var elt = document.getElementById(elementId);

        if (elt.selectedIndex == -1)
            return null;
        try {
            var opts = elt.options;
            for(var opt, j = 0; opt = opts[j]; j++) {
                if(opt.value == value) {
                    sel.selectedIndex = j;
                    break;
                }
            }
        }
        catch(err) {
            elt.value = value;
        }
    }

    function save() { 
            var username = getSelectedText('username');
            var password = getSelectedText('password');
            var type = getSelectedText('type');
            var queue = getSelectedText('queue');
            window.location.href = '/process?action=save&username=' + username + '&password=' + password + '&type=' + type + '&queue=' + queue;
    }

    function post() { 
            var content = getSelectedText('content');
            var queue = getSelectedText('queue');
            window.location.href = '/process?action=post&queue=' + queue + '&content=' + encodeURI(content);
    }

    function edit(username, type, queue) { 
            setSelectedText('username', username);
            
            setSelectedText('queue', queue);
            if(type == 'admin') { 
                setSelectedText('type', 'Administrator');   
            }
            else {
                setSelectedText('type', 'MQ User');   
            }
    }

    function msgbox(text, redirect) {
        if (confirm(text)) {
            window.location.href = redirect
        } else {
            // Do nothing!
        }
    }

    </script>
    </head>
    <body>
    $BODY$
    </body>
    </html>
    """

@auth.verify_password
def verify_password(username_or_token, password):
    """
    Verify user password
    """

    # first try to authenticate by token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.query.filter_by(username=username_or_token).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True


@management.route('/view', methods=['GET'])
@auth.login_required
def get_view():
    """
    Management: show the queue
    """
    try:
        queue = request.args.get('queue')
        messages = Message.query.filter_by(queue=queue)

        content = Style.STYLE_MQS_BACK_BUTTON
        content = content + Style.STYLE_MQS_INPUTBOX.replace('$QUEUE$', queue)
        content = content + Style.STYLE_MQS_START.replace('$QUEUE$', queue)

        for message in messages:
            date = None
            try:
                date = unicode(message.created).split('.')[0]
            except:
                date = ''
            content = content + Style.STYLE_MQS_ROW.replace('$ID$', str(message.id)).replace('$MSG$', message.message).replace('$DATE$', date).replace('$QUEUE$', queue)

        content = content + Style.STYLE_MQS_END
        page = Style.BASIC_PAGE.replace('$TITLE$', 'Queue ' + queue).replace('$BODY$', content)

        return page
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@management.route('/process', methods=['GET'])
@auth.login_required
def get_post():
    """
    Management: process. 
    Can be:
        - save: saves a queue or user
        - delete: deletes a queue or user
        - post: add a message
        - delete_msg: deletes a message
    """
    action = request.args["action"]
    page = Style.BASIC_RETURN.replace('$URL$', '/index')

    if action == 'save':
        username = request.args["username"]
        password = request.args["password"]
        type = request.args["type"]
        queue = request.args["queue"]

        if username is None or password is None or queue is None:
            return page    # missing arguments

        exists = User.query.filter_by(username=username).first()

        if exists is not None:
            # update if existing

            # update a username
            if exists.username != username:
                exists.username = username
                messages = Message.query.filter_by(queue=queue)
                for message in messages:
                    message.username = username
                    db.session.add(message)
                    db.session.commit()

            # update the password
            if exists.password_hash != exists.hash_password(password) and password != '':
                exists.hash_password(password)

            # update the queue
            if exists.queue != queue:
                exists.queue = queue
                messages = Message.query.filter_by(queue=queue)
                for message in messages:
                    message.queue = queue
                    db.session.add(message)
                    db.session.commit()
       
            db.session.add(exists)
            db.session.commit()

            return page    # existing user

        if type.lower() == 'administrator':
            user = User(username=username, queue='')
            user.hash_password(password)
            db.session.add(user)
            db.session.commit()
        else:
            user = User(username=username, queue=queue)
            user.hash_password(password)
            db.session.add(user)
            db.session.commit()
    if action == 'delete':
        username = request.args["username"]
        try:
            user = User.query.filter_by(username=username).first()
            if not user:
                return page

            db.session.delete(user)
            db.session.commit()

            return page
        except:
            return page
    if action == 'post':
        queue = request.args["queue"]
        content = request.args["content"]
        page = Style.BASIC_RETURN.replace('$URL$', '/view?queue=' + queue)

        user = User.query.filter_by(queue=queue).first()
        if user is None:
            return page

        message = Message(queue=queue, username=user.username, message=content)
        db.session.add(message)
        db.session.commit()
        return page

    if action == 'delete_msg':
        id = request.args["id"]
        message = Message.query.get(id)

        db.session.delete(message)
        db.session.commit()

        queue = request.args["queue"]
        page = Style.BASIC_RETURN.replace('$URL$', '/view?queue=' + queue)
        return page

    return page


@management.route('/', methods=['GET'])
@auth.login_required
def get_root():
    return redirect("/index", code=302)


@management.route('/index', methods=['GET'])
@auth.login_required
def get_index():
    # get all users
    users = User.query.all()

    adminusers = Style.STYLE_ADMIN_HEADER
    messagequeues = Style.STYLE_MESSAGES_HEADER

    # weed through all mq's and users
    for user in users:
        if user.queue == None or user.queue == '':
            # admin user
            adminusers = adminusers + '<tr><td>' + str(user.id) + '</td><td>' + user.username + '</td><td><a onclick="edit(\'' + user.username + '\', \'admin\', \'\')"><img class="edit" /></a><a onclick="msgbox(\'Do you want to delete user: ' + user.username + '?\',\'/process?action=delete&username=' + user.username + '\')"><img class="delete" /></a></td></tr>'
        else:
            # mq user
            messages = Message.query.filter_by(queue=user.queue).count()
            messagequeues = messagequeues + '<tr><td>' + str(user.id) + '</td><td>' + user.username + '</td><td>' + user.queue + '</td><td>' + str(messages) + '</td><td><a onclick="edit(\'' + user.username + '\', \'\', \'' + user.queue + '\')"><img class="edit" /></a><a onclick="msgbox(\'Do you want to delete user: ' + user.username + '?\',\'/process?action=delete&username=' + user.username + '\')"><img class="delete" /></a><a href="/view?queue=' + user.queue + '"><img class="magnify" /></a></td></tr>'
    
    adminusers = adminusers + Style.STYLE_ADMIN_FOOTER
    messagequeues = messagequeues + Style.STYLE_MESSAGES_FOOTER


    adding = '<h2>Add User & Queue</h2><table class="gridtable"><tr><td>Username</td><td><input type="text" id="username" name="username"></td></tr><tr><td>Password</td><td><input id="password" type="password" name="password"></td></tr><tr><td>Type</td><td><select id="type" onchange="getSelectedText(\'type\')"><option id="type" selected="">MQ User</option><option>Administrator</option></select></td></tr><tr><td>Queue</td><td><input id="queue" type="text" name="queue"></td></tr><tr><td></td><td><button onclick="save()">Save</button></td></tr></table>' 

    content = ''
    if request.args.get('edit') is not None:
        content = '<h2>Administrators</h2>' + adminusers + '<h2>Queues</h2>' + messagequeues + adding

        content = content + '<h2>Edit</h2>'
    else:
        content = '<h2>Administrators</h2>' + adminusers + '<h2>Queues</h2>' + messagequeues + adding

    page = Style.BASIC_PAGE.replace('$TITLE$', 'Monitor').replace('$BODY$', content)

    return page

@management.route('/install', methods=['POST'])
def post_install():
    try:
        users = User.query.all()

        if len(users) == 0:
            username = request.json.get('username')
            password = request.json.get('password')
            if username is None or password is None:
                abort(400)    # missing arguments

            if User.query.filter_by(username=username).first() is not None:
                abort(400)    # existing user

            user = User(username=username, queue='')
            user.hash_password(password)
            db.session.add(user)
            db.session.commit()

            return (jsonify({'username': user.username}), 201,
                {'Location': url_for('get_user', id=user.id, _external=True)})
        else:
            return (jsonify({}), 400)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@management.route('/install', methods=['GET'])
def get_install():
    try:
        users = User.query.all()

        if len(users) == 0:
            username = request.args.get('username')
            password = request.args.get('password')
            if username is None or password is None:
                abort(400)    # missing arguments

            if User.query.filter_by(username=username).first() is not None:
                abort(400)    # existing user

            user = User(username=username, queue='')
            user.hash_password(password)
            db.session.add(user)
            db.session.commit()

            return (jsonify({'username': user.username}), 201,
                {'Location': url_for('get_user', id=user.id, _external=True)})
        else:
            return (jsonify({}), 400)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@management.route('/api/users', methods=['GET'])
@auth.login_required
def get_users():
    try:
        users = User.query.all()

        results = []
        for user in users:
            results.append(user.username)

        return jsonify({'usernames': results})
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@management.route('/api/users', methods=['POST'])
@auth.login_required
def new_user():
    try: 
        username = request.json.get('username')
        password = request.json.get('password')
        queue = request.json.get('queue')

        if username is None or password is None or queue is None:
            abort(400)    # missing arguments

        if User.query.filter_by(username=username).first() is not None:
            abort(400)    # existing user

        user = User(username=username, queue=queue)
        user.hash_password(password)
        db.session.add(user)
        db.session.commit()

        return (jsonify({'username': user.username}), 201,
                {'Location': url_for('get_user', id=user.id, _external=True)})
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)


@management.route('/api/users/<int:id>', methods=['GET'])
@auth.login_required
def get_user(id):
    try:
        user = User.query.get(id)
        if not user:
            abort(400)
        return jsonify({'username': user.username})
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@app.route('/api/version')
def get_version():
    return jsonify({'version': 'beta-1'})

@app.route('/api/token')
@auth.login_required
def get_auth_token():
    try:
        token = g.user.generate_auth_token(600)
        return jsonify({'token': token.decode('ascii'), 'duration': 600})
    except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            print ''.join('!! ' + line for line in lines)  # Log it or whatever here
            abort(503)

@app.route('/api/msg/<string:queue>', methods=['POST'])
@auth.login_required
def post_msg(queue):
    try:
        if User.query.filter_by(username=g.user.username, queue=queue).first() is None:
            abort(400)    # not authorized

        data = request.json

        if data == None:
            data = request.data
        else:
            data = json.dumps(data)

        message = Message(queue=queue, username=g.user.username, message=data)
        db.session.add(message)
        db.session.commit()

        return (jsonify({'id': message.id}), 201)
    except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            print ''.join('!! ' + line for line in lines)  # Log it or whatever here
            abort(503)


@app.route('/api/msg/<string:queue>', methods=['GET'])
@auth.login_required
def get_msg(queue):
    try:
        if User.query.filter_by(username=g.user.username, queue=queue).first() is None:
            abort(400)    # not authorized

        messages = Message.query.filter_by(queue=queue)

        result = []
        for message in messages:
            result.append(json.dumps({'id': message.id, 'queue': message.queue, 'username': message.username, 'message': message.message}))
    
        return (jsonify(messages = result), 200)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@app.route('/api/clear/<string:queue>', methods=['GET'])
@auth.login_required
def clear_msg(queue):
    try:
        if User.query.filter_by(username=g.user.username, queue=queue).first() is None:
            abort(400)    # not authorized

        messages = Message.query.filter_by(queue=queue)

        result = []
        for message in messages:
            db.session.delete(message)
            db.session.commit()
        
        return (jsonify({}), 202)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@app.route('/api/truncate/<string:queue>', methods=['GET'])
@auth.login_required
def truncate_msg(queue):
    try:
        if User.query.filter_by(username=g.user.username, queue=queue).first() is None:
            abort(400)    # not authorized

        messages = Message.query.filter_by(queue=queue)

        deletes = []
        last = None
        for message in messages:
            if last == None:
                last = message
            else:
                pass
                if message.created > last.created:
                    # new last
                    deletes.append(last)
                    last = message
                else:
                    deleteds.append(message)

        for delete in deletes:
            db.session.delete(delete)
            db.session.commit()
        
        return (jsonify({}), 202)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

@app.route('/api/msg/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_msg(id):
    try:
        usr = User.query.filter_by(username=g.user.username).first()
        if usr  is None:
            abort(400)    # not authorized

        message = Message.query.get(id)

        if message.queue != usr.queue:
            abort(400)
    
        if message == None:
            return (jsonify({}), 204)

        db.session.delete(message)
        db.session.commit()

        return (jsonify({'id': message.id}), 202)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join('!! ' + line for line in lines)  # Log it or whatever here
        abort(503)

def app_thread():
    # run app on port 80
    app.run(host='0.0.0.0',port=80, debug=True, use_reloader=False)

def management_thread():
    # run mgmt on 8888
    management.run(host='0.0.0.0',port=8888, debug=True, use_reloader=False)

if __name__ == '__main__':
    key = 'ThisIsMySuperSecretKey'

    app.config['SECRET_KEY'] = key
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

    management.config['SECRET_KEY'] = key
    management.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    management.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
    management.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

    # in case the database doesn't exists: make it
    if not os.path.exists('db.sqlite'):
        db.create_all()

    # start an app thread and a mgmt thread
    appthread = threading.Timer(1, app_thread)
    mgmtthread = threading.Timer(1, management_thread)

    while True:
        # keep a loop, if one of the threads gets killed: revive it
        if not appthread.isAlive():
            print 'App thread dead, starting...'

            appthread = threading.Timer(1, app_thread)
            appthread.start()

        if not mgmtthread.isAlive():
            print 'Management thread dead, starting...'

            mgmtthread = threading.Timer(1, management_thread)
            mgmtthread.start()

        time.sleep(5)




