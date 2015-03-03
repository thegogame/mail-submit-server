
import logging
import logging.handlers
import mailbox
import requests
import json
import sys
from datetime import datetime
from dateutil import tz
import re
import os
import urllib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.message import Message


#===DEV===#
# API_URL = 'http://localhost:5051/api/'
# LOG_FILE = '/Users/gogamedesign/code/mail-submit/logs/parse-maildir.log'
# MAILDIR = '/Users/gogamedesign/code/mail-submit/Maildir'
# SIGN_URL = 'http://localhost:5051/sign?bucket=%s&key=uploads%%2F%s'
# UPLOAD_BUCKET = "gogame-breadcrumb-media-uploads-dev"

#===PRODUCTION===#
API_URL = 'http://play.thegogame.com/api/'
LOG_FILE = '/home/ubuntu/mailsubmit/logs/parse-maildir.log'
MAILDIR = '/home/ubuntu/Maildir'
SIGN_URL = 'http://play.thegogame.com/sign?bucket=%s&key=uploads%%2F%s'
UPLOAD_BUCKET = "gogame-breadcrumb-media-uploads"

ACCEPT_MIME_TYPES = [
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'video/mp4', 'video/mpeg', 
    'video/quicktime', 'video/mov', 'video/3gpp',
    'video/ogg', 'video/x-flv', 'video/webm', 'video/avi'
]
UPLOAD_URL = 'http://%s.s3.amazonaws.com' % UPLOAD_BUCKET

EMAIL_SENDER = 'media@thegogame.com'
EMAIL_RECIPIENTS = ['rob@thegogame.com']

update_media_params = {
  "media_item": {
    "in_gallery": "true",
    "is_uploaded": 'false',
    "media_bucket": UPLOAD_BUCKET,
    "media_size": 0,
    "media_timestamp": 0,
    "media_type": "image", 
    "upload_bucket": UPLOAD_BUCKET,
    "upload_key": "",
    "upload_mime_type": "image/jpeg"
  }, 
  "status": "started"
}

log = logging.getLogger('ParseLog')
log.setLevel(logging.DEBUG)
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10000, backupCount=10)
log.addHandler(handler)

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def filter_spam(maildir):
    '''Currently only filters email sent to all@thegogame.com'''
    keys = maildir.keys()
    for i, mail in enumerate(maildir):
        key = keys[i]
        been_there = mail.get_all('X-BeenThere')
        if been_there and 'all@thegogame.com' in been_there:
            maildir.discard(key)   

def send_error_email(bad_mail, error):
    '''
    Create a new mail to tech@thegogame and sender.
    Inform of failure to parse.
    Include minimal info from bad mail and any attachments.
    '''
    COMMASPACE = ', '
    new_mail = MIMEMultipart()
    new_mail['Subject'] = 'Mail parse error'
    new_mail['From'] = EMAIL_SENDER
    new_mail['To'] = COMMASPACE.join(EMAIL_RECIPIENTS + [bad_mail.get('From')])
    text = '''
Darn it! 
Unfortunately an error occured while trying to parse the following mail. 
Please contact your game runner immediately for resolution.

From: %s
Subject: %s
Error: %s
Mail ▾
'''
    body = Message()
    body.set_payload(text % (
        bad_mail.get('From'), 
        bad_mail.get('Subject'), 
        error
    ))
    new_mail.attach(body)

    # attach bad mail
    if bad_mail.is_multipart():
        for m in bad_mail.get_payload():
            new_mail.attach(m)
    else:
        new_mail.attach(bad_mail)

    try:
        smtpObj = smtplib.SMTP('localhost')
        smtpObj.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, new_mail.as_string())
        log.info("Successfully sent error notification email")
    except smtplib.SMTPException:
        msg = "Unable to send error notification email"
        log.error(msg)
        raise ParseError(msg)


def is_valid_waypoint_id(id):
    # todo: better validation
    return len(id) == 24

# def is_valid_pin(pin):
#     return len(pin) == 3

def api_get(query, raise_exception=True):
    '''Make a GET request to Breadcrumb API'''
    log.info('api_get: %s' % query)
    response = requests.get(API_URL + query)
    if not response.status_code == requests.codes.ok:
        msg = 'api_get to %s failed for reason %s' % (
            query, response.status_code)
        log.error(msg)
        if raise_exception:
            raise ParseError(msg)
        else:
            return {}
    return json.loads(response.text)

# def get_pin(mail):
#     '''parse login pin from mail'''
#     pin = mail['Subject']
#     if not is_valid_pin(pin):
#         # handle invalids
#         return None
#     return pin

def get_waypoint_id(mail):
    # parse waypoint id from subject line
    waypoint_id = None
    reg = re.compile(r'{{missionID=(\w+)}}')
    match = reg.search(mail['Subject'])
    if match:
        waypoint_id = match.groups()[0];
    return waypoint_id

def get_media_timestamp(utcnow):
    # relies on system time being correct for timezone
    return int((utcnow - datetime(1970, 1, 1)).total_seconds())

def utc_to_local(datetime_utc, tzname):
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz(tzname)
    datetime_utc = datetime_utc.replace(tzinfo=from_zone)
    return datetime_utc.astimezone(to_zone)

def slugify(text): 
    if not text: 
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^a-zA-Z0-9\s\-]+', '', text)
    text = re.sub(r'\-', " ", text)
    text = re.sub(r'\s+', "-", text)
    return text

def get_upload_key(waypoint_id, now, fext):
    response = api_get('objects/waypoints/%s' % waypoint_id)
    waypoint = response['waypoint']
    missions = response['missions']
    playthroughID = waypoint['playthrough_id']
    response = api_get('objects/playthroughs/%s' % playthroughID)
    playthrough = response['playthrough']
    strpfmt = "%Y-%m-%dT%H:%M:%SZ" 
    started_at_utc = datetime.strptime(playthrough['started_at'], strpfmt)
    started_at_local = utc_to_local(started_at_utc, 'America/Los_Angeles') 
    playthrough_date = started_at_local.strftime("%Y-%m-%d")
    playthrough_time = started_at_local.strftime("%I-%M")

    response = api_get('objects/games/%s' % playthrough['game_id'])
    game = response['game']
    game_name = slugify(game.get('name') or playthroughID)

    teamID = waypoint['team_id']
    response = api_get('objects/teams/%s' % teamID)
    team = response['team']
    team_name = slugify(team.get('name') or teamID)

    mission = missions[0]
    mission_name = slugify(mission.get('name'))

    timestamp = now.strftime("%Y-%m-%d-%I-%M-%S")

    return '%s/%s-%s/%s/%s-%s%s' % (
        playthrough_date, game_name, playthrough_time,
        team_name, mission_name, timestamp, fext
    )

def update_media(waypoint_id, media_params):
    log.info('update_media waypoint_id: %s' % waypoint_id)
    log.debug('media params: %s' % media_params)
    response = requests.post(API_URL + 
        'events/waypoints/%s/trigger_action' % waypoint_id, data={
            'name': 'update_media',
            'params': json.dumps(media_params)
        }
    )
    if not response.status_code == requests.codes.ok:
        msg = 'update_media failure: %s' % response.text
        log.error(msg)
        raise ParseError(msg)

def upload_media(payload, upload_key, content_type):
    '''upload to S3'''
    # get signature
    key = urllib.quote(upload_key, safe="~()*!.\'")
    response = requests.get(SIGN_URL % (UPLOAD_BUCKET, key))
    if not response.status_code == requests.codes.ok:
        msg = 'upload_media sign failure'
        log.error(msg)
        raise ParseError(msg)
    signature = json.loads(response.text)
    signature.update({"content-type": content_type})
    upload_name = os.path.basename(upload_key)
    files = {'file': (upload_name, payload.decode('base64'))}
    response = requests.post(UPLOAD_URL, data=signature, files=files)
    if not '<Location>' in response.text:
        msg = 'upload_media failure: %s' % response.text
        log.error(msg)
        raise ParseError(msg)

def parse_msg(msg, waypoint_id):
    '''msg class = email.message.Message'''
    content_type = msg.get_content_type() 
    log.info('parse_msg of content_type %s' % content_type)
    if content_type not in ACCEPT_MIME_TYPES:
        log.warn('Attachment mime type unacceptable')
        return
    payload = msg.get_payload()
    media_size = sys.getsizeof(payload)
    if not payload or media_size < 10:
        log.warn('Attachment has no content')
        return

    media_type = content_type.split('/')[0]
    upload_mime_type = content_type
    filename = msg.get_filename()
    utcnow = datetime.utcnow()
    media_timestamp = get_media_timestamp(utcnow)
    fname, fext = os.path.splitext(filename)

    upload_key = get_upload_key(waypoint_id, utcnow, fext)

    update_media_params.update({"status": 'started'})
    update_media_params['media_item'].update({
        "media_type": media_type,
        "media_size": media_size,
        "media_timestamp": media_timestamp,
        "upload_mime_type": upload_mime_type,
        "upload_key": upload_key,
        "in_gallery": "true"           
    })
    # update - started
    update_media(waypoint_id, update_media_params)

    # upload
    upload_media(payload, upload_key, upload_mime_type)

    # update - uploaded
    update_media_params.update({"status": 'uploaded'})
    update_media(waypoint_id, update_media_params)

def parse_mail(mail):
    '''mail = mailbox.MaildirMessage'''
    log.info('From: %s' % mail['From'])

    waypoint_id = get_waypoint_id(mail)
    if not waypoint_id:
        msg = 'Waypoint ID not found'
        log.warn(msg)
        send_error_email(mail, msg)
        return # temporary for debugging : REMOVE ?
        # raise ParseError(msg)
    response = api_get('objects/waypoints/%s' % waypoint_id,
        raise_exception=False)
    if not response.has_key('waypoint'):
        msg = 'Invalid waypoint ID'
        log.warn(msg)
        return # temporary for debugging : REMOVE ?
        # raise ParseError(msg)
    if not mail.is_multipart():
        msg = 'No attachment(s)'
        log.warn(msg)
        raise ParseError(msg)

    # parse attachment(s)
    for msg in mail.get_payload():
        parse_msg(msg, waypoint_id)

def parse_maildir():
    maildir = mailbox.Maildir(MAILDIR, factory=None)
    filter_spam(maildir)
    if len(maildir) < 1:
        maildir.clean()
        return
    
    log.info('Running parse_maildir')
    now = datetime.now()
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
    log.info(timestamp)

    log.info('%d new mail in %s' % (len(maildir), MAILDIR))
    keys = maildir.keys()
    for i, mail in enumerate(maildir):
        log.info('Parsing mail #%d' % (i + 1))
        key = keys[i]
        try: 
            parse_mail(mail)
        except Exception as e:
            send_error_email(mail, str(e))
            raise e
        # maildir.discard(key)

    maildir.clean()
    log.info('Finished.\n\n')

if __name__ == '__main__':
    parse_maildir()
