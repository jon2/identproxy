# identproxy

This is an RFC1413 (Identification Protocol, or IDENT) proxy for pfSense
It listens on the public interface, checks the NAT table to figure out
which private-side system the request belongs to, and forwards the
request to that system.  It then proxies the response back to the
requestor.
IDENT is a stupid protocol, but some people still want to use it.

This is the first Python script I ever wrote.  It's probably defective
in multiple ways.