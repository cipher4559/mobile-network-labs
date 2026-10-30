"""Minimal BER / TCAP codec (ITU-T X.690 + Q.773) - no deps."""


def enc_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def tlv(tag, content):
    return bytes([tag]) + enc_len(len(content)) + content


def integer(v, tag=0x02):
    if v == 0:
        return tlv(tag, b"\x00")
    b = v.to_bytes((v.bit_length() + 8) // 8, "big", signed=True)
    return tlv(tag, b)


def seq(*parts):
    return tlv(0x30, b"".join(parts))


# ---- TCAP (Q.773) ----------------------------------------------------------
# Begin [APPLICATION 2]=0x62, End [APPLICATION 4]=0x64, Continue=0x65
# otid [APPLICATION 8]=0x48, componentPortion [APPLICATION 12]=0x6C
# components use context tags: Invoke=0xA1, ReturnResultNotLast=0xA2,
# ReturnResultLast=0xA3, ReturnError=0xA4, Reject=0xA5

def invoke(invoke_id, opcode, param=b""):
    return tlv(0xA1, integer(invoke_id) + integer(opcode) + param)


def return_result_last(invoke_id, opcode, param=b""):
    return tlv(0xA3, integer(invoke_id) + seq(integer(opcode) + param))


def return_error(invoke_id, errcode, param=b""):
    return tlv(0xA4, integer(invoke_id) + integer(errcode) + param)


def begin(otid, *components):
    return tlv(0x62, tlv(0x48, otid) + tlv(0x6C, b"".join(components)))


def end(otid, *components):
    return tlv(0x64, tlv(0x48, otid) + tlv(0x6C, b"".join(components)))


def cont(otid, *components):
    return tlv(0x65, tlv(0x48, otid) + tlv(0x6C, b"".join(components)))


# ---- decoder ---------------------------------------------------------------

def parse_tlv(buf, i=0):
    tag = buf[i]
    i += 1
    ln = buf[i]
    i += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(buf[i:i + n], "big")
        i += n
    return tag, buf[i:i + ln], i + ln


def iter_tlv(content):
    i = 0
    while i < len(content):
        tag, val, i = parse_tlv(content, i)
        yield tag, val


def as_int(b):
    return int.from_bytes(b, "big", signed=True)


def parse_tcap(pdu):
    """Return {'type','otid','components':[{'kind','id','opcode','param'}]}."""
    tag, body, _ = parse_tlv(pdu)
    names = {0x62: "Begin", 0x64: "End", 0x65: "Continue", 0x67: "Abort"}
    out = {"type": names.get(tag, "0x%02x" % tag), "otid": None, "components": []}
    for t, v in iter_tlv(body):
        if t == 0x48:
            out["otid"] = v
        elif t == 0x6C:
            for ct, cv in iter_tlv(v):
                comp = {"kind": {0xA1: "Invoke", 0xA2: "ReturnResultNotLast",
                                 0xA3: "ReturnResultLast", 0xA4: "ReturnError",
                                 0xA5: "Reject"}.get(ct, "0x%02x" % ct)}
                comp.update(_parse_component(comp["kind"], cv))
                out["components"].append(comp)
    return out


def _parse_component(kind, cv):
    if kind == "Invoke":
        _, iid_b, i = parse_tlv(cv, 0)
        _, op_b, j = parse_tlv(cv, i)
        return {"id": as_int(iid_b), "opcode": as_int(op_b), "param": cv[j:]}
    if kind in ("ReturnResultLast", "ReturnResultNotLast"):
        _, iid_b, i = parse_tlv(cv, 0)
        _, inner, _ = parse_tlv(cv, i)             # SEQUENCE
        _, op_b, j = parse_tlv(inner, 0)
        return {"id": as_int(iid_b), "opcode": as_int(op_b), "param": inner[j:]}
    if kind == "ReturnError":
        _, iid_b, i = parse_tlv(cv, 0)
        _, erc, j = parse_tlv(cv, i)
        return {"id": as_int(iid_b), "errcode": as_int(erc), "param": cv[j:]}
    return {"raw": cv}


def _skip(buf, n):
    i = 0
    for _ in range(n):
        _, _, i = parse_tlv(buf, i)
    return i


def hexdump(b, width=16):
    lines = []
    for off in range(0, len(b), width):
        chunk = b[off:off + width]
        hx = " ".join("%02x" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append("%04x  %-*s  %s" % (off, width * 3 - 1, hx, asc))
    return "\n".join(lines)
