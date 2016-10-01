#Copyright (c) 2016, Jon Green
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the <organization> nor the
#    names of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written permission.

#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
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
        output = subprocess.check_output(["/sbin/pfctl", "-ss"], shell=False, stderr=None)
        match = re.findall(r".*tcp (.+):{} \((.+):(.+)\) -> (.+):{}.*".format(p1,p2), output)
        if match:
                server = match[0][1]
                p1 = int(match[0][2])
        return [server, p1, p2]

def sendRequest(server, port1, port2):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
                sock.connect((server, 113))
                print "DEBUG: Connecting to {}".format(server)
                sock.send("{} , {}\n".format(port1,port2))
                response = sock.recv(1024)
                print "DEBUG: Response = {}".format(response)
        except:
                return
        finally:
                sock.close()
        return(response)

class myHandler(SocketServer.StreamRequestHandler):

        def handle(self):
                request = self.rfile.readline().strip()
                print "DEBUG: Received request: {}".format(request)

                # Check for sanity and extract ports
                sane = True
                validInput = re.match('^(\d+)(|\s),(|\s)(\d+)$', request)
                if validInput:
                        # Looks like valid input - extract the port numbers
                        p1 = int(validInput.group(1))
                        p2 = int(validInput.group(4))
 
                        # Ports in valid range?
                        r = range(1,65535)
                        if p1 not in r or p2 not in r:
                                sane = False
                else:
                        sane = False

                if sane == False:
                        print "DEBUG: Invalid input received ({})".format(request)
                        response = "{}:ERROR:NO-USER".format(request)
                        self.wfile.write(response)
                        return

                print "DEBUG: Made it past sanity checking"

                # Look up ports in NAT table
                natList = natLookup(p1, p2)
                print "DEBUG: NAT table server: {}, serverport: {}, remoteport: {}\n".format(natList[0], natList[1], natList[2]) 

                if not natList:
                        print "DEBUG: NAT entry not found"
                        response = "{}:ERROR:NO-USER".format(request)
                        self.wfile.write(response)
                        return

                # Send IDENT request to private-side server
                serverResponse = sendRequest(natList[0], natList[1], natList[2])
                
                # If there was a response, forward it back to the original requestor
                if not serverResponse:
                        print "DEBUG: Didn't get response from private-side server"
                        response = "{}:ERROR:NO-USER".format(request)
                        self.wfile.write(response)
                        return

                print "DEBUG: Sending response: {}".format(serverResponse)
                self.wfile.write(serverResponse)

                
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        pass

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 113
                
    server = ThreadedTCPServer((HOST, PORT), myHandler)

    # Run forever
    server.serve_forever()

