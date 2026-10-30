"""MAP (TS 29.002) operations: TBCD codecs, argument/result builders,
and validation/decoding through pycrate's 3GPP ASN.1 tree."""
import sys

from ss7 import tlv, seq, integer, hexdump


# ---- TBCD helpers ----------------------------------------------------------

def isdn(num, noi=0x91):
    """AddressString: 0x91 (international) / 0x81 (national) + TBCD digits."""
    digits = [int(c) for c in num.lstrip("+")]
    if len(digits) % 2:
        digits.append(0xF)
    out = bytearray([noi])
    for i in range(0, len(digits), 2):
        out.append((digits[i + 1] << 4) | digits[i])
    return bytes(out)


def imsi(imsi_str):
    """IMSI: TBCD digits, no nature-of-address octet."""
    digits = [int(c) for c in imsi_str]
    if len(digits) % 2:
        digits.append(0xF)
    out = bytearray()
    for i in range(0, len(digits), 2):
        out.append((digits[i + 1] << 4) | digits[i])
    return bytes(out)


def bcd_str(b):
    """Render an AddressString / IMSI TBCD value as text."""
    s = ""
    for byte in b[1:] if b and b[0] in (0x91, 0x81) else b:
        lo, hi = byte & 0x0F, byte >> 4
        for nib in (lo, hi):
            if nib != 0xF:
                s += str(nib)
    return ("+" if b and b[0] == 0x91 else "") + s


# ---- argument builders -----------------------------------------------------

def sri_sm_arg(msisdn, sc):
    return seq(tlv(0x80, isdn(msisdn)),
               tlv(0x81, b"\xff"),                 # sm-RP-PRI = TRUE
               tlv(0x82, isdn(sc)))


def sai_arg(imsi_str):
    return seq(tlv(0x80, imsi(imsi_str)), integer(1))


def ul_arg(imsi_str, msc, vlr):
    # UpdateLocationArg: imsi and vlr-Number are untagged OCTET STRING
    return seq(tlv(0x04, imsi(imsi_str)),
               tlv(0x81, isdn(msc)),
               tlv(0x04, isdn(vlr)))


def psi_arg(imsi_str):
    # requestedInfo [2]; locationInformation [0] is a NULL marker (presence = ask)
    return seq(tlv(0x80, imsi(imsi_str)),
               tlv(0xA2, tlv(0x80, b"")))


# ---- result builders -------------------------------------------------------

def sri_sm_res(imsi_str, msc_nnn):
    # RoutingInfoForSM-Res { imsi (untagged), locationInfoWithLMSI [0] }
    return seq(tlv(0x04, imsi(imsi_str)),
               tlv(0xA0, tlv(0x81, isdn(msc_nnn))))


def sai_res(*_a, **_k):
    raise NotImplementedError("triplet encoding left as an exercise")


def ul_res(hlr=None):
    return seq(tlv(0x04, isdn(hlr))) if hlr else seq()


def psi_res(vlr, age=0):
    # ProvideSubscriberInfoRes { subscriberInfo { locationInformation {
    #   ageOfLocationInformation, vlr-number } } }
    loc = integer(age) + tlv(0x81, isdn(vlr))
    return seq(seq(tlv(0xA0, loc)))


OPS = {
    2:  ("updateLocation",          ul_arg,   ul_res,          "UpdateLocation"),
    45: ("sendRoutingInfoForSM",    sri_sm_arg, sri_sm_res,    "RoutingInfoForSM"),
    56: ("sendAuthInfo",            sai_arg,  sai_res,         "SendAuthInfo"),
    70: ("provideSubscriberInfo",   psi_arg,  psi_res,         "ProvideSubscriberInfo"),
}


# ---- pycrate bridge --------------------------------------------------------

def _map_ctx():
    import pycrate_mobile.TS29002_MAPAppCtx as A
    return A


def validate(opcode, pdu, kind="ArgumentType"):
    """Decode with the real 3GPP ASN.1; raises if our BER is malformed."""
    A = _map_ctx()
    t = A.get_operation(opcode)[0][kind]
    t.from_ber(pdu)
    return t.get_val()


def human(opcode, val):
    if not isinstance(val, dict):
        return repr(val)
    out = {}
    for k, v in val.items():
        if isinstance(v, (bytes, bytearray)) and k in ("msisdn", "imsi",
                                                       "networkNode-Number",
                                                       "vlr-number", "vlr-Number", "hlr-Number", "msc-Number",
                                                       "serviceCentreAddress"):
            out[k] = bcd_str(bytes(v))
        elif isinstance(v, dict):
            out[k] = human(opcode, v)
        else:
            out[k] = v
    return out


def dump_dialogue(pdu, note=""):
    from ss7 import parse_tcap
    d = parse_tcap(pdu)
    print("  TCAP %s  otid=%s" % (d["type"],
                                  d["otid"].hex() if d["otid"] else "-"))
    for c in d["components"]:
        name = OPS.get(c.get("opcode"), ("?",))[0]
        print("    %-16s id=%s op=%s (%s)  param=%d bytes"
              % (c["kind"], c.get("id"), c.get("opcode"), name,
                 len(c.get("param", b""))))
    if note:
        print("   ", note)


if __name__ == "__main__":
    # self-test: encode then validate every argument
    cases = [
        (45, sri_sm_arg("+15551234567", "+15551234500")),
        (56, sai_arg("001010123456789")),
        (2,  ul_arg("001010123456789", "+15550001111", "+15550002222")),
        (70, psi_arg("001010123456789")),
    ]
    ok = True
    for op, arg in cases:
        try:
            val = validate(op, arg)
            print("op %-3d %-24s OK  %s" % (op, OPS[op][0], human(op, val)))
        except Exception as e:
            ok = False
            print("op %-3d %-24s FAIL %s: %s" % (op, OPS[op][0],
                                                 type(e).__name__, str(e)[:80]))
            print(hexdump(arg))
    sys.exit(0 if ok else 1)
