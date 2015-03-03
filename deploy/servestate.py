
from StateHTTPRequestHandler import StateRequestHandler
from BaseHTTPServer import HTTPServer
import sys

SERVER_IP = '127.0.0.1'
DEFAULT_PORT = 8000


def serve():
    """
    Run an HTTP server at 127.0.0.1
    (port = 8000 or the first command line argument)
    """

    port = DEFAULT_PORT
    if sys.argv[1:]:
        port = int(sys.argv[1])
    server_address = (SERVER_IP, port)

    httpd = HTTPServer(server_address, StateRequestHandler)

    sa = httpd.socket.getsockname()
    print "Serving State over HTTP on", sa[0], "port", sa[1], "..."
    httpd.serve_forever()


if __name__ == '__main__':
    serve()