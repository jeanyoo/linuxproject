from flask import Flask, render_template, request, redirect, \
    jsonify, url_for, flash
from sqlalchemy import create_engine, asc, desc, and_
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Resource, User

# New imports to create anti forgery state token
from flask import session as login_session
import random
import string
import datetime

# Imports to Gconnect. Needed to call signincallback method
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(open('/var/www/catalog/catalog/client_secrets1.json',
                            'r').read())['web']['client_id']


# Connect to Database and create database session
engine = create_engine('postgresql://catalog:12345@localhost/catalog')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create a state token to prevent request forgery
# Store it in the session for later validation
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# Create server side function to call signincallback
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # If validated, then obtain one-time authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('/var/www/catalog/catalog/client_secrets1.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade '
                                            'the authorization code'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/'
           'tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps('Token user ID not '
                                            'a match to user ID'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps('Token client ID not '
                                            'a match to app'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check to see if user is already logged into system
    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('User is already '
                                            'connected'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # If above is not true, store the access token for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info using google api
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()

    # From retrieved user info, take fields app needs
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # See if user exists, if not make a new user account
    user_id = getUserID(login_session['email'])
    if user_id is None:
        createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;' \
              '-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# User helper functions

def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
        user = session.query(User).filter_by(id=user_id).one()
        return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Disconnect user and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    print 'access token is'
    print access_token
    print 'User name is'
    print login_session['username']
    if access_token is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Execute HTTP GET request to revoke current token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is'
    print result

    if result['status'] == '200':
        # Reset the user's session
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid
        response = make_response(json.dumps('Failed to revoke token'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view resource information
@app.route('/catalog/<topicname>/JSON')
def catalogTopicJSON(topicname):
    resources = session.query(Resource).filter_by(topic=topicname).all()
    return jsonify(TopicItems=[i.serialize for i in resources])


# Show 10 latest added resources
@app.route('/')
@app.route('/catalog/')
def showCatalog():
    catalog = session.query(Resource).order_by(Resource.created_date.desc())\
        .limit(10).all()
    if 'username' not in login_session:
        return render_template('publicCatalog.html', catalog=catalog)
    else:
        return render_template('catalog.html', catalog=catalog)


# Show all resources relevant to topic
@app.route('/catalog/<topicname>/')
def showResources(topicname):
    resources = session.query(Resource).filter_by(topic=topicname).all()
    if 'username' not in login_session:
        return render_template('publicResources.html',
                               resources=resources, topicname=topicname)
    else:
        return render_template('resources.html',
                               resources=resources, topicname=topicname)


# Show details on the chosen resource item
@app.route('/catalog/<topicname>/<resourcename>/<int:resource_id>/')
def showItem(topicname, resourcename, resource_id):
    resource = session.query(Resource).filter_by(id=resource_id).one()
    if 'username' not in login_session:
        return render_template('publicDescription.html', resource=resource)
    else:
        return render_template('Description.html', resource=resource)


# Create a new resource item - only for users who logged in
@app.route('/catalog/new/', methods=['GET', 'POST'])
def newResource():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newResource = Resource(name=request.form['name'],
                               description=request.form['description'],
                               topic=request.form['topic'],
                               created_date=datetime.datetime.
                               strptime(request.form['created_date'],
                                        '%Y-%m-%d'),
                               user_id=login_session['user_id'])
        session.add(newResource)
        session.commit()
        flash('New resource item %s successfully created!' % newResource.name)
        return redirect(url_for('showCatalog'))
    else:
        return render_template('newResource.html')


# Edit an existing resource item
@app.route('/catalog/<topicname>/<resourcename>/<int:resource_id>/edit/',
           methods=['GET', 'POST'])
def editResource(topicname, resourcename, resource_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedResource = session.query(Resource).filter_by(id=resource_id).one()

    if login_session['user_id'] != editedResource.user_id:
        return "<script>function myFunction(){" \
               "alert('You are not authorized to edit this item!');" \
               "window.location.href = '/catalog';}</script>" \
               "<body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedResource.name = request.form['name']
        if request.form['description']:
            editedResource.description = request.form['description']
        if request.form['topic']:
            editedResource.topic = request.form['topic']
        session.add(editedResource)
        session.commit()
        flash('Resource successfully edited to %s !' % editedResource.name)
        return redirect(url_for('showCatalog'))
    else:
        return render_template('editResource.html', resource=editedResource)


# Delete an existing resource item
@app.route('/catalog/<topicname>/<resourcename>/<int:resource_id>/delete/',
           methods=['GET', 'POST'])
def deleteResource(topicname, resourcename, resource_id):
    if 'username' not in login_session:
        return redirect('/login')
    deletedResource = session.query(Resource).filter_by(id=resource_id).one()

    if deletedResource.user_id != login_session['user_id']:
        return "<script>function myFunction(){" \
               "alert('You are not authorized to delete this item!');" \
               "window.location.href = '/catalog'; }</script>" \
               "<body onload='myFunction()''>"

    if request.method == 'POST':
        session.delete(deletedResource)
        flash('%s successfully deleted!' % deletedResource.name)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        return render_template('deleteResource.html', resource=deletedResource)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
