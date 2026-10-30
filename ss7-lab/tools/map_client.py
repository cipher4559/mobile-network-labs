"""MAP client: walks a full SRISM -> PSI -> UpdateLocation dialogue against
the mock HLR and prints every layer. Nothing touches a real network.

Modes:
  (default)   one full four-operation dialogue, verbosely
  --quiet     one line per operation
  --repeat N  repeat the dialogue N times (a legitimate retry storm or a burst)
  --sweep N   ask provideSubscriberInfo for N different IMSIs from one source
"""
import argparse
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


def call(op, arg, label, quiet=False):
    otid = os.urandom(4)
    req = begin(otid, invoke(1, op, arg))
    print("\n=== %s (op %d)" % (label, op))
    print("request  %d bytes" % len(req))
    if not quiet:
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
    if not quiet:
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


def dialogue(quiet=False):
    call(45, m.sri_sm_arg("+15551234567", SC),
         "SRISM  sendRoutingInfoForSM  (where to deliver an SMS)", quiet)
    call(70, m.psi_arg(IMSI),
         "PSI    provideSubscriberInfo (where is the subscriber)", quiet)
    call(2, m.ul_arg(IMSI, MSC, VLR),
         "UL     updateLocation        (roaming attach)", quiet)
    call(56, m.sai_arg(IMSI),
         "SAI    sendAuthInfo          (auth vectors)", quiet)


def sweep(n, quiet=False):
    for i in range(n):
        imsi = "00101012345%04d" % i
        call(70, m.psi_arg(imsi), "PSI    provideSubscriberInfo %s" % imsi, quiet)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true",
                    help="one line per operation (skip hexdumps)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="repeat the four-operation dialogue N times")
    ap.add_argument("--sweep", type=int, default=0,
                    help="query N different IMSIs from this one source")
    args = ap.parse_args()
    if args.sweep:
        sweep(args.sweep, args.quiet)
    else:
        for _ in range(max(1, args.repeat)):
            dialogue(args.quiet)
    print("\nTCAP/MAP dialogue complete; transport here is TCP framing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
