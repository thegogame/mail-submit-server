
__version__ = "0.1"

from BaseHTTPServer import BaseHTTPRequestHandler
import supervisor.xmlrpc
import xmlrpclib


class StateRequestHandler(BaseHTTPRequestHandler):

    '''
    Implements only HTTP GET requests for named processes' state
    /state/<process_name>
    Uses xmlrpc proxy to talk to supervisor through socketpath
    Note that socketpath is hard-coded
    Returns 200 OK if process.statename == RUNNING
    '''

    server_version = "StateHTTP/" + __version__

    def __init__(self, request, client_address, server):
        self.protocol_version = "HTTP/1.0"
        # setup xmlprc proxy
        self.socketpath = '/home/ubuntu/mailsubmit/supervisor.sock'
        self.proxy = xmlrpclib.ServerProxy('http://127.0.0.1',
            transport=supervisor.xmlrpc.SupervisorTransport(None, None,
                serverurl='unix://' + self.socketpath))
        BaseHTTPRequestHandler.__init__(self, request, client_address, server);


    def do_GET(self):
        # validate path
        path = self.path
        process_name = path.split('/')[-1]
        if not process_name or process_name == 'state':
            self.send_error(400, 
                "Bad request syntax: use /state/<process_name>")
            return

        # ensure supervisor is running
        supervisor_state = self.proxy.supervisor.getState()
        if not supervisor_state or supervisor_state['statename'] != 'RUNNING':
            self.send_error(500, 
                "Supervisor is not running")
            return           

        # check if process is running
        process_state = None
        try:
            process_state = self.proxy.supervisor.getProcessInfo(process_name)
        except xmlrpclib.Fault:
            self.send_error(500, 
                "No process named %s" % process_name)
            return
        if not process_state or process_state['statename'] != 'RUNNING':
            self.send_error(500, 
                "Process %s is not running" % process_name)
            return

        self.send_response(200, 'OK')
        self.send_header("Content-type", 'text/plain')
        self.end_headers()
 
