# Copyright (c) 2016, Jon Green
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# This is an RFC1413 (Identification Protocol, or IDENT) proxy for pfSense
# It listens on the public interface, checks the NAT table to figure out
# which private-side system the request belongs to, and forwards the
# request to that system.  It then proxies the response back to the
# requestor.
# IDENT is a stupid protocol, but some people still want to use it.
#
# This is the first Python script I ever wrote.  It's probably defective
# in multiple ways.


import SocketServer
import socket
import threading
import re
import subprocess


def natLookup(p1, p2):
        # Given an input of two TCP port numbers (p1 is the pfSense local port,
        # p2 is the remote port), search the pf session state to determine
        # which IP address on the private side owns the connection,
        # and which TCP source port it is using.
        # Returns the private-side IP address and the two port numbers that
        # the private-side machine is using.
        output = subprocess.check_output(["/sbin/pfctl", "-ss"],
                                         shell=False, stderr=None).split("\n")
        pattern = re.compile(r".*tcp .+:(\d+) \((.+):(\d+)\) -> .+:(\d+).*")
        for line in output:
                match = pattern.match(line)
                if match:
                        if (int(match.group(1)) == p1 and
                                int(match.group(4)) == p2):
                                server = match.group(2)
                                p1 = int(match.group(3))
                                return [server, p1]
        return


def sendRequest(server, port1, port2):
        # Given an IP address and two port numbers, craft an RFC1413-compliant
        # request and send it to the private-side IP address
        # Returns whatever response came back
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
                sock.connect((server, 113))
                print "DEBUG: Connecting to %s" % server
                sock.send("{} , {}\n".format(port1, port2))
                response = sock.recv(1024)
                print "DEBUG: Response = %s" % response
        except Exception as e:
                return
        finally:
                sock.close()
        return response


class myHandler(SocketServer.StreamRequestHandler):
        # This is where all the work happens
        def handle(self):
                request = self.rfile.readline().strip()
                print "DEBUG: Received request: %s" % request

                # Check for sanity and extract ports
                sane = True
                validInput = re.match('^(\d+)(|\s),(|\s)(\d+)$', request)
                if validInput:
                        # Looks like valid input - extract the port numbers
                        p1 = int(validInput.group(1))
                        p2 = int(validInput.group(4))

                        # Ports in valid range?
                        if p1 < 1 or p1 > 65535 or p2 < 1 or p2 > 65535:
                                sane = False
                else:
                        sane = False

                if not sane:
                        print "DEBUG: Invalid input received (%s)" % request
                        response = request + ":ERROR:NO-USER"
                        self.wfile.write(response)
                        return

                print "DEBUG: Made it past sanity checking"

                # Look up ports in NAT table
                natList = natLookup(p1, p2)

                if not natList:
                        print "DEBUG: NAT entry not found"
                        response = request + ":ERROR:NO-USER"
                        self.wfile.write(response)
                        return

                server = natList[0]
                p1 = natList[1]

                print ("DEBUG: NAT table server: %s" % server +
                       "serverport: %d, remoteport: %d\n" % (p1, p2))

                # Send IDENT request to private-side server
                serverResponse = sendRequest(server, p1, p2)

                # If there was a response, forward it back to the original
                # requestor
                if not serverResponse:
                        print ("DEBUG: Didn't get response from " +
                               "private-side server")
                        response = request + ":ERROR:NO-USER"
                        self.wfile.write(response)
                        return

                print "DEBUG: Sending response: %s" % serverResponse
                self.wfile.write(serverResponse)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        pass

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 113

    server = ThreadedTCPServer((HOST, PORT), myHandler)

    # Run forever
    server.serve_forever()
