"""MAP client: walks a full SRISM -> PSI -> UpdateLocation dialogue against
the mock HLR and prints every layer. Nothing touches a real network."""
import os
import socket
import struct
import sys

from ss7 import begin, hexdump, parse_tcap, invoke
import mapops as m

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3899"))

IMSI = os.environ.get("IMSI", "001010123456789")
MSC = "+15550001111"
VLR = "+15550002222"
SC = "+15551234500"


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def call(op, arg, label):
    otid = os.urandom(4)
    req = begin(otid, invoke(1, op, arg))
    print("\n=== %s (op %d)" % (label, op))
    print("request  %d bytes" % len(req))
    print(hexdump(req))
    try:
        print("decoded request arg:", m.human(op, m.validate(op, arg)))
    except Exception as e:
        print("REQUEST ARG INVALID:", e)
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(struct.pack(">I", len(req)) + req)
        ln = struct.unpack(">I", recv_exact(s, 4))[0]
        resp = recv_exact(s, ln)
    print("response %d bytes" % len(resp))
    print(hexdump(resp))
    d = parse_tcap(resp)
    for c in d["components"]:
        if c["kind"] == "ReturnError":
            print("  <- ReturnError id=%d local=%d" % (c["id"], c.get("errcode", -1)))
            continue
        try:
            val = m.validate(c["opcode"], c["param"], "ResultType")
            print("  <- ReturnResultLast id=%d op=%d" % (c["id"], c["opcode"]))
            print("     result:", m.human(c["opcode"], val))
        except Exception as e:
            print("  <- result decode failed:", e)


def main():
    call(45, m.sri_sm_arg("+15551234567", SC),
         "SRISM  sendRoutingInfoForSM  (where to deliver an SMS)")
    call(70, m.psi_arg(IMSI),
         "PSI    provideSubscriberInfo (where is the subscriber)")
    call(2, m.ul_arg(IMSI, MSC, VLR),
         "UL     updateLocation        (roaming attach)")
    call(56, m.sai_arg(IMSI),
         "SAI    sendAuthInfo          (auth vectors)")
    print("\nTCAP/MAP dialogue complete; transport here is TCP framing.")


if __name__ == "__main__":
    sys.exit(main())
