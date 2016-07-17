import logging
import json
import base64
import urllib
import google.appengine.api.urlfetch as urlfetch

from flask import Flask, Response, request
from firebase.wrapper import Firebase

try:
    # Apparently not all implementations have SystemRandom defined, so I expect
    # this import to fail, if that's the case.
    from random import SystemRandom
    randomizer = SystemRandom()
except:
    import random as randomizer

import datetime, time

SAFE_ALPHABET_STRING = '234679CDFGHJKMNPRTWXYZ'
SAFE_ALPHABET = list(SAFE_ALPHABET_STRING)

app = Flask(__name__)

API_VERSION = 'v0.1'

# for Ana
@app.route('/')
def hello():
    return 'Hello Ana :P :D'

# incoming channels

@app.route('/api/%s/new' % API_VERSION, methods=['POST'])
def web_incoming():
  request.get_json(force=True)

  incident = request.json
  if 'status' not in incident:
    incident['status'] = 'reported'
  incident = persist_incident(incident)

  response=Response(response=json.dumps(incident),
    status=200,
    mimetype="application/json")
  return response


@app.route('/api/%s/sparrowsms' % API_VERSION, methods=['GET'])
def sparrowsms_incoming():
  incident_info = {
    'sender_channel':'sms',
    'sender_id' : request.args.get('from','')
  }
  incident = {
    'incident_info':incident_info,
    'additional_info':{
      'message': request.args.get('text','')
    },
    'status':'reported'
  }
  incident = persist_incident(incident)

  return 'We will get back to you asap!', 200

@app.route('/api/%s/mailgun' % API_VERSION, methods=['POST'])
def mailgun_incoming():
  incident_info = {
    'sender_channel':'email',
    'sender_id' : request.form['sender']
  }
  incident = {
    'incident_info':incident_info,
    'additional_info':{
      'message': request.form['stripped-text']
    },
    'status':'reported'
  }
  incident = persist_incident(incident)
  return 'success', 200


# TODO add parameter for incident id and call ack_incident(incident_id)
@app.route('/api/%s/ack' % API_VERSION)
def acknowledge_incident():

  return 'success', 200

@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', 500

# --- app logic --- #

# persist incident in Firebase
def persist_incident(incident):

  incident['incident_id'] = safe_generate()
  incident['incident_time'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
  incident['updated_time'] = incident['incident_time']

  firebase = Firebase('https://call-1098.firebaseio.com/incidents/%s.json'%incident['incident_id'], None)
  firebase.set(incident)

  if incident['status'] == 'reported':
    create_alert(incident)
  return incident

# create alert object in Firebase
def create_alert(incident):
  firebase = Firebase('https://call-1098.firebaseio.com/alerts/%s.json'%incident['incident_id'], None)
  alert = {
      'incident_id': incident['incident_id'],
      'incident_time': incident['incident_time'],
      'sender_id': incident['incident_info']['sender_id'],
      'sender_channel': incident['incident_info']['sender_channel'],
      'additional_info': incident['additional_info']
  }
  firebase.set(alert)
  send_alert(alert)
  return

# send alert to recipients
def send_alert(alert):
  # add output channels
  #sparrowsms_alert(alert)
  android_alert(alert)
  mailgun_alert(alert)
  return

# TODO currently not working
def sparrowsms_alert(alert):
  alert_text = 'Incident ID: %s, %s from %s' % (alert['incident_id'],alert['sender_channel'],alert['sender_id'])
  sms_alert = {'token' : 'FKIdRWsOEUr2U3jj8KVN',
      'from'  : 'Demo',
      'to'    : '9823710002',
      'text'  : alert_text}
  r = urlfetch.fetch(
    "http://api.sparrowsms.com/v2/sms/",
    method=urlfetch.POST,
    payload=sms_alert,
    headers={
      'Content-Type': 'application/json; charset=utf-8'
    })
  logging.info(r.__dict__)
  return

# TODO currently not working
def mailgun_alert(alert):
  mail_title = "'Incident ID: %s, %s from %s' % (alert['incident_id'],alert['sender_channel'],alert['sender_id'])"
  mail_text = alert['additional_info']['message']

  r = urlfetch.fetch(
  "https://api.mailgun.net/v3/1098helpline.org/messages",
    method=urlfetch.POST,
    payload=urllib.urlencode({
      'from':'incident@1098helpline.org',
      'to':['hostirosti@gmail.com'],
      'subject':mail_title,
      'text':mail_text
    }),
    headers={
      'Content-Type': 'application/json; charset=utf-8',
      'Authorization':'Basic %s' % base64.b64encode('api:key-ce5f54a880db4e650fb04c3bd87e3074')
    })
  logging.info(r.__dict__)
  return

def android_alert(alert):
  alert_text = 'Incident ID: %s, %s from %s' % (alert['incident_id'],alert['sender_channel'],alert['sender_id'])
  android_alert_post = {
     'to' : 'eGNGeZAIn6M:APA91bHsarTm41mgZY2146r5wusotcMCrkFbww86ec4dElSjPJ4L1xN1CKdclI6zxSSXCHeOs4wMtNkpGI-RLN0dtoirOpjnzwO-leTDEzJhVsWG6eA94cjbdui27GFGZbkz1dv3Nn9H',
     'notification' : {
       'body' : alert_text,
       'title' : '1098 Helpline',
       'icon' : 'myicon'
     }
  }
  r = urlfetch.fetch(
    "https://fcm.googleapis.com/fcm/send",
    method=urlfetch.POST,
    payload=json.dumps(android_alert_post),
    headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Authorization':'key=AIzaSyAIJQteETIeimhbLo7hMs3KXSiq77dLq3E'
            })
  return

# ack incident => set status to received and delete alert object in Firebase
def ack_incedent(incident_id):
  alert = Firebase('https://call-1098.firebaseio.com/alerts/%s.json'%incident_id, None)
  alert.remove()
  incidents = Firebase('https://call-1098.firebaseio.com/incidents/%s.json'%incident_id, None)
  incident = incidents.get()
  incident['status'] = 'received'
  incident['updated_time'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
  incidents.update(incident)
  return

def safe_generate(length=8):
    """This generates a random travel-style record locator using the safe
    alphabet. """

    return ''.join(randomizer.choice(SAFE_ALPHABET) for i in range(0, length))

@app.after_request
def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
  return response

# [END app]