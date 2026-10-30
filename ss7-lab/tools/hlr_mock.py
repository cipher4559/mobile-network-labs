"""Mock HLR: answers MAP operations over a length-prefixed TCAP dialogue.

Educational only - it is not connected to any network. Every invoke is also
appended to an audit log (run/hlr_audit.jsonl) so tools/query_monitor.py can
demonstrate rate-based detection on the same telemetry a real HLR or SS7
firewall would expose.
"""
import json
import os
import socket
import time

from ss7 import parse_tcap, end, return_result_last, return_error, hexdump
import mapops as m

BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3899"))
IMSI = os.environ.get("IMSI", "001010123456789")
NNN = os.environ.get("NNN", "+15550001111")     # MSC/SMS-IW MSC number
VLR = os.environ.get("VLR", "+15550002222")
AUDIT = os.environ.get("AUDIT", "run/hlr_audit.jsonl")


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def recv_frame(sock):
    (ln,) = __import__("struct").unpack(">I", recv_exact(sock, 4))
    return recv_exact(sock, ln)


def send_frame(sock, pdu):
    sock.sendall(len(pdu).to_bytes(4, "big") + pdu)


def _text(value):
    """IMSI/MSISDN arrive as bytes from the ASN.1 decoder; make them printable."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return m.bcd_str(value) or value.hex()
    return str(value)


def audit(rec):
    """Append one JSON line. Never let logging break the dialogue."""
    try:
        d = os.path.dirname(AUDIT)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(AUDIT, "a") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    except OSError:
        pass


def answer(op, arg):
    """Return (kind, payload): kind 'res' -> result BER, 'err' -> error code."""
    if op == 45:                                   # sendRoutingInfoForSM
        return "res", m.sri_sm_res(IMSI, NNN)
    if op == 70:                                   # provideSubscriberInfo
        return "res", m.psi_res(VLR, 12)
    if op == 2:                                    # updateLocation
        return "res", m.ul_res(VLR)
    if op == 56:                                   # sendAuthInfo
        return "err", 3                            # systemFailure (demo)
    return "err", 3


def handle(conn, addr):
    src = "%s:%d" % addr
    pdu = recv_frame(conn)
    d = parse_tcap(pdu)
    print("<- TCAP %s otid=%s (%d bytes)" % (d["type"],
          d["otid"].hex() if d["otid"] else "-", len(pdu)))
    comps = []
    for c in d["components"]:
        if c["kind"] != "Invoke":
            continue
        op = c["opcode"]
        name = m.OPS.get(op, ("unknown",))[0]
        msisdn = None
        imsi = None
        try:
            arg = m.validate(op, c["param"])
            print("   invoke id=%d op=%d %s" % (c["id"], op, name))
            print("   arg: %s" % m.human(op, arg))
        except Exception as e:
            print("   invoke id=%d op=%d  decode failed: %s" % (c["id"], op, e))
            audit({"ts": round(time.time(), 3), "src": src, "op": op,
                   "imsi": None, "msisdn": None, "result": "err"})
            comps.append(return_error(c["id"], 3))
            continue
        if isinstance(arg, dict):
            imsi = arg.get("imsi")
            msisdn = arg.get("msisdn")
        if op == 45:
            # SRISM takes an MSISDN; the HLR resolves it to the stored IMSI.
            imsi = IMSI
        kind, payload = answer(op, arg if isinstance(arg, dict) else {})
        audit({"ts": round(time.time(), 3), "src": src, "op": op,
               "imsi": _text(imsi), "msisdn": _text(msisdn), "result": kind})
        if kind == "res":
            comps.append(return_result_last(c["id"], op, payload))
        else:
            comps.append(return_error(c["id"], payload))
    reply = end(d["otid"] or b"\x00\x00\x00\x01", *comps)
    print("-> TCAP End (%d bytes)" % len(reply))
    print(hexdump(reply))
    send_frame(conn, reply)


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((BIND, PORT))
    srv.listen(5)
    print("mock HLR listening on %s:%d (imsi=%s nnn=%s vlr=%s)"
          % (BIND, PORT, IMSI, NNN, VLR))
    print("audit log: %s" % AUDIT)
    while True:
        conn, addr = srv.accept()
        print("-- connection from %s:%d" % addr)
        try:
            handle(conn, addr)
        except Exception as e:
            import traceback; traceback.print_exc()
        finally:
            conn.close()


if __name__ == "__main__":
    main()
