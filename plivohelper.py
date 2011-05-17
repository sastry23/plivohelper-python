# -*- coding: utf-8 -*-

__VERSION__ = "0.1"

import urllib, urllib2, base64, hmac
from hashlib import sha1
from xml.dom.minidom import Document

try:
    from google.appengine.api import urlfetch
    APPENGINE = True
except:
    APPENGINE = False


class PlivoException(Exception): pass

# Plivo REST Helpers
# ===========================================================================

class HTTPErrorProcessor(urllib2.HTTPErrorProcessor):
    def https_response(self, request, response):
        code, msg, hdrs = response.code, response.msg, response.info()
        if code >= 300:
            response = self.parent.error(
                'http', request, response, code, msg, hdrs)
        return response

class HTTPErrorAppEngine(Exception): pass

class PlivoUrlRequest(urllib2.Request):
    def get_method(self):
        if getattr(self, 'http_method', None):
            return self.http_method
        return urllib2.Request.get_method(self)

class REST:
    """Plivo helper class for making
    REST requests to the Plivo API.  This helper library works both in
    standalone python applications using the urllib/urlib2 libraries and
    inside Google App Engine applications using urlfetch.
    """
    def __init__(self, url, id, token):
        """initialize a object

        url: Rest API Url
        id: Plivo SID/ID
        token: Plivo token

        returns a Plivo object
        """
        self.url = url
        self.id = id
        self.token = token
        self.opener = None

    def _build_get_uri(self, uri, params):
        if params and len(params) > 0:
            if uri.find('?') > 0:
                if uri[-1] != '&':
                    uri += '&'
                uri = uri + urllib.urlencode(params)
            else:
                uri = uri + '?' + urllib.urlencode(params)
        return uri

    def _urllib2_fetch(self, uri, params, method=None):
        # install error processor to handle HTTP 201 response correctly
        if self.opener == None:
            self.opener = urllib2.build_opener(HTTPErrorProcessor)
            urllib2.install_opener(self.opener)

        if method and method == 'GET':
            uri = self._build_get_uri(uri, params)
            req = PlivoUrlRequest(uri)
        else:
            req = PlivoUrlRequest(uri, urllib.urlencode(params))
            if method and (method == 'DELETE' or method == 'PUT'):
                req.http_method = method

        authstring = base64.encodestring('%s:%s' % (self.id, self.token))
        authstring = authstring.replace('\n', '')
        req.add_header("Authorization", "Basic %s" % authstring)

        response = urllib2.urlopen(req)
        return response.read()

    def _appengine_fetch(self, uri, params, method):
        if method == 'GET':
            uri = self._build_get_uri(uri, params)

        try:
            httpmethod = getattr(urlfetch, method)
        except AttributeError:
            raise NotImplementedError(
                "Google App Engine does not support method '%s'" % method)

        authstring = base64.encodestring('%s:%s' % (self.id, self.token))
        authstring = authstring.replace('\n', '')
        r = urlfetch.fetch(url=uri, payload=urllib.urlencode(params),
            method=httpmethod,
            headers={'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': 'Basic %s' % authstring})
        if r.status_code >= 300:
            raise HTTPErrorAppEngine("HTTP %s: %s" % \
                (r.status_code, r.content))
        return r.content

    def request(self, path, method=None, vars={}):
        """sends a request and gets a response from the Plivo REST API

        path: the URL (relative to the endpoint URL, after the /v1
        method: the HTTP method to use, defaults to POST
        vars: for POST or PUT, a dict of data to send

        returns Plivo response in XML or raises an exception on error
        """
        if not path or len(path) < 1:
            raise ValueError('Invalid path parameter')
        if method and method not in ['GET', 'POST', 'DELETE', 'PUT']:
            raise NotImplementedError(
                'HTTP %s method not implemented' % method)

        if path[0] == '/':
            uri = self.url + path
        else:
            uri = self.url + '/' + path

        if APPENGINE:
            return self._appengine_fetch(uri, vars, method)
        return self._urllib2_fetch(uri, vars, method)

    def call(self, call_params):
        """REST Call Helper
        """
        path = '/v0.1/Call/'
        method = 'POST'
        return self.request(path, method, call_params)

    def bulk_call(self, call_params):
        """REST Bulk Call Helper
        """
        path = '/v0.1/BulkCalls/'
        method = 'POST'
        return self.request(path, method, call_params)

    def transfer_call(self, call_params):
        """REST Transfer Live Call Helper
        """
        path = '/v0.1/TransferCall/'
        method = 'POST'
        return self.request(path, method, call_params)

    def hangup_call(self, call_params):
        """REST Hangup Live Call Helper
        """
        path = '/v0.1/HangupCall/'
        method = 'POST'
        return self.request(path, method, call_params)

    def hangup_all_calls(self):
        """REST Hangup All Live Calls Helper
        """
        path = '/v0.1/HangupAllCalls/'
        method = 'GET'
        return self.request(path, method)

    def schedule_hangup(self, call_params):
        """REST Schedule Hangup Helper
        """
        path = '/v0.1/ScheduleHangup/'
        method = 'GET'
        return self.request(path, method, call_params)

    def cancel_scheduled_hangup(self, call_params):
        """REST Cancel a Scheduled Hangup Helper
        """
        path = '/v0.1/CancelScheduledHangup/'
        method = 'GET'
        return self.request(path, method, call_params)


# RESTXML Response Helpers
# ===========================================================================

class Grammar:
    """Plivo basic grammar object.
    """
    def __init__(self, **kwargs):
        self.name = self.__class__.__name__
        self.body = None
        self.nestables = None

        self.grammar = []
        self.attrs = {}
        for k, v in kwargs.items():
            if k == "sender": k = "from"
            if v != None: self.attrs[k] = unicode(v)

    def __repr__(self):
        """
        String representation of a grammar
        """
        doc = Document()
        return self._xml(doc).toxml()

    def _xml(self, root):
        """
        Return an XML element representing this grammar
        """
        grammar = root.createElement(self.name)

        # Add attributes
        keys = self.attrs.keys()
        keys.sort()
        for a in keys:
            grammar.setAttribute(a, self.attrs[a])

        if self.body:
            text = root.createTextNode(self.body)
            grammar.appendChild(text)

        for c in self.grammar:
            grammar.appendChild(c._xml(root))

        return grammar


    def append(self, grammar):
        if not self.nestables:
            raise PlivoException("%s is not nestable" % self.name)
        if grammar.name not in self.nestables:
            raise PlivoException("%s is not nestable inside %s" % \
                (grammar.name, self.name))
        self.grammar.append(grammar)
        return grammar

    def asUrl(self):
        return urllib.quote(str(self))

    def addSpeak(self, text, **kwargs):
        return self.append(Speak(text, **kwargs))

    def addPlay(self, url, **kwargs):
        return self.append(Play(url, **kwargs))

    def addWait(self, **kwargs):
        return self.append(Wait(**kwargs))

    def addRedirect(self, url=None, **kwargs):
        return self.append(Redirect(url, **kwargs))

    def addHangup(self, **kwargs):
        return self.append(Hangup(**kwargs))

    def addReject(self, **kwargs):
        return self.append(Reject(**kwargs))

    def addGetDigits(self, **kwargs):
        return self.append(GetDigits(**kwargs))

    def addNumber(self, number, **kwargs):
        return self.append(Number(number, **kwargs))

    def addDial(self, number=None, **kwargs):
        return self.append(Dial(number, **kwargs))

    def addRecord(self, **kwargs):
        return self.append(Record(**kwargs))

    def addConference(self, name, **kwargs):
        return self.append(Conference(name, **kwargs))

    def addSms(self, msg, **kwargs):
        return self.append(Sms(msg, **kwargs))

    def addRecordSession(self, **kwargs):
        return self.append(RecordSession(**kwargs))

    def addPreAnswer(self, **kwargs):
        return self.append(PreAnswer(**kwargs))

    def addScheduleHangup(self, **kwargs):
        return self.append(ScheduleHangup(**kwargs))

class Response(Grammar):
    """Plivo response object.

    version: Plivo API version 0.1
    """
    def __init__(self, version=None, **kwargs):
        Grammar.__init__(self, version=version, **kwargs)
        self.nestables = ['Speak', 'Play', 'GetDigits', 'Record', 'Dial',
            'Redirect', 'Wait', 'Hangup', 'Reject', 'Sms', 'RecordSession',
            'PreAnswer', 'ScheduleHangup', 'Conference']

class Speak(Grammar):
    """Speak text

    text: text to say
    voice: voice to be used based on TTS engine
    language: language to use
    loop: number of times to say this text
    """
    ENGLISH = 'en'
    SPANISH = 'es'
    FRENCH = 'fr'
    GERMAN = 'de'

    def __init__(self, text, voice=None, language=None, loop=None, **kwargs):
        Grammar.__init__(self, voice=voice, language=language, loop=loop,
            **kwargs)
        self.body = text
        if language and (language != self.ENGLISH and language != self.SPANISH
            and language != self.FRENCH and language != self.GERMAN):
            raise PlivoException( \
                "Invalid Say language parameter, must be " + \
                "'en', 'es', 'fr', or 'de'")

class Play(Grammar):
    """Play audio file at a URL

    url: url of audio file, MIME type on file must be set correctly
    loop: number of time to say this text
    """
    def __init__(self, url, loop=None, **kwargs):
        Grammar.__init__(self, loop=loop, **kwargs)
        self.body = url

class Wait(Grammar):
    """Wait for some time to further process the call

    length: length of wait time in seconds
    """
    def __init__(self, length=None, **kwargs):
        Grammar.__init__(self, length=length, **kwargs)

class Redirect(Grammar):
    """Redirect call flow to another URL

    url: redirect url
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, url=None, method=None, **kwargs):
        Grammar.__init__(self, method=method, **kwargs)
        if method and (method != self.GET and method != self.POST):
            raise PlivoException( \
                "Invalid method parameter, must be 'GET' or 'POST'")
        self.body = url

class Hangup(Grammar):
    """Hangup the call
    """
    def __init__(self, **kwargs):
        Grammar.__init__(self)

class GetDigits(Grammar):
    """Get digits from the caller's keypad

    action: URL to which the digits entered will be sent
    method: submit to 'action' url using GET or POST
    numDigits: how many digits to gather before returning
    timeout: wait for this many seconds before returning
    finishOnKey: key that triggers the end of caller input
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, action=None, method=None, numDigits=None, timeout=None,
        finishOnKey=None, **kwargs):

        Grammar.__init__(self, action=action, method=method,
            numDigits=numDigits, timeout=timeout, finishOnKey=finishOnKey,
            **kwargs)
        if method and (method != self.GET and method != self.POST):
            raise PlivoException( \
                "Invalid method parameter, must be 'GET' or 'POST'")
        self.nestables = ['Speak', 'Play', 'Wait']

class Number(Grammar):
    """Specify phone number in a nested Dial element.

    number: phone number to dial
    sendDigits: key to press after connecting to the number
    """
    def __init__(self, number, sendDigits=None, **kwargs):
        Grammar.__init__(self, sendDigits=sendDigits, **kwargs)
        self.body = number

class Sms(Grammar):
    """ Send a Sms Message to a phone number

    to: whom to send message to, defaults based on the direction of the call
    sender: whom to send message from.
    action: url to request after the message is queued
    method: submit to 'action' url using GET or POST
    statusCallback: url to hit when the message is actually sent
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, msg, to=None, sender=None, method=None, action=None,
        statusCallback=None, **kwargs):
        Grammar.__init__(self, action=action, method=method, to=to, sender=sender,
            statusCallback=statusCallback, **kwargs)
        if method and (method != self.GET and method != self.POST):
            raise PlivoException( \
                "Invalid method parameter, must be GET or POST")
        self.body = msg

class Conference(Grammar):
    """Specify conference in a nested Dial element.

    name: friendly name of conference
    muted: keep this participant muted (bool)
    beep: play a beep when this participant enters/leaves (bool)
    startConferenceOnEnter: start conf when this participants joins (bool)
    endConferenceOnExit: end conf when this participants leaves (bool)
    waitUrl: TwiML url that executes before conference starts
    waitMethod: HTTP method for waitUrl GET/POST
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, name, muted=None, beep=None,
        startConferenceOnEnter=None, endConferenceOnExit=None, waitUrl=None,
        waitMethod=None, **kwargs):
        Grammar.__init__(self, muted=muted, beep=beep,
            startConferenceOnEnter=startConferenceOnEnter,
            endConferenceOnExit=endConferenceOnExit, waitUrl=waitUrl,
            waitMethod=waitMethod, **kwargs)
        if waitMethod and (waitMethod != self.GET and waitMethod != self.POST):
            raise PlivoException( \
                "Invalid waitMethod parameter, must be GET or POST")
        self.body = name

class Dial(Grammar):
    """Dial another phone number and connect it to this call

    action: submit the result of the dial to this URL
    method: submit to 'action' url using GET or POST
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, number=None, action=None, method=None, **kwargs):
        Grammar.__init__(self, action=action, method=method, **kwargs)
        self.nestables = ['Number']
        if number and len(number.split(',')) > 1:
            for n in number.split(','):
                self.append(Number(n.strip()))
        else:
            self.body = number
        if method and (method != self.GET and method != self.POST):
            raise PlivoException( \
                "Invalid method parameter, must be GET or POST")

class Record(Grammar):
    """Record audio from caller

    action: submit the result of the dial to this URL
    method: submit to 'action' url using GET or POST
    maxLength: maximum number of seconds to record
    timeout: seconds of silence before considering the recording complete
    """
    GET = 'GET'
    POST = 'POST'

    def __init__(self, action=None, method=None, maxLength=None,
                 timeout=None, **kwargs):
        Grammar.__init__(self, action=action, method=method, maxLength=maxLength,
            timeout=timeout, **kwargs)
        if method and (method != self.GET and method != self.POST):
            raise PlivoException( \
                "Invalid method parameter, must be GET or POST")

class Reject(Grammar):
    """Reject an incoming call

    reason: message to play when rejecting a call
    """
    REJECTED = 'rejected'
    BUSY = 'busy'

    def __init__(self, reason=None, **kwargs):
        Grammar.__init__(self, reason=reason, **kwargs)
        if reason and (reason != self.REJECTED and reason != self.BUSY):
            raise PlivoException( \
                "Invalid reason parameter, must be BUSY or REJECTED")

class RecordSession(Grammar):
    """Record the call session
    """
    def __init__(self, prefix=None, **kwargs):
        Grammar.__init__(self, prefix=None, **kwargs)

class ScheduleHangup(Grammar):
    """Schedule Hangup of call after a certain time
    """
    def __init__(self, time=None, **kwargs):
        Grammar.__init__(self, time=time, **kwargs)

class PreAnswer(Grammar):
    """Answer the call in Early Media Mode and execute nested grammar
    """
    def __init__(self, time=None, **kwargs):
        Grammar.__init__(self, time=time, **kwargs)
        self.nestables = ['Play', 'Speak', 'GetDigits']


# Plivo Utility function and Request Validation
# ===========================================================================

class Utils:
    def __init__(self, id, token):
        """initialize a plivo utility object

        id: Plivo account SID/ID
        token: Plivo account token

        returns a Plivo util object
        """
        self.id = id
        self.token = token

    def validateRequest(self, uri, postVars, expectedSignature):
        """validate a request from plivo

        uri: the full URI that Plivo requested on your server
        postVars: post vars that Plivo sent with the request
        expectedSignature: signature in HTTP X-Plivo-Signature header

        returns true if the request passes validation, false if not
        """

        # append the POST variables sorted by key to the uri
        s = uri
        if len(postVars) > 0:
            for k, v in sorted(postVars.items()):
                s += k + v

        # compute signature and compare signatures
        return (base64.encodestring(hmac.new(self.token, s, sha1).digest()).\
            strip() == expectedSignature)
