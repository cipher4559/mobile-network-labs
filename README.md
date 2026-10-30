# mobile-network-labs

Two small, hands-on mobile-network labs that run entirely on your own machine:

| Lab | What it is | Protocols you actually see |
|-----|------------|----------------------------|
| [`5g-lab/`](5g-lab/) | Open5GS 5G core + UERANSIM UE/gNB in Docker | 5G-AKA, NAS, NGAP, PFCP, GTP-U over a fake test PLMN |
| [`ss7-lab/`](ss7-lab/) | Osmocom STP/HLR/MSC/BSC/MGW + a MAP/TCAP mock HLR | M3UA, SCTP, SCCP, BSSMAP, GSUP, MAP over TCAP, ASN.1/BER |

They are deliberately complementary: the 5G core is the modern, HTTP-based
service architecture; the SS7 lab is the legacy signalling network that 2G/3G
cores still use. Reading them side by side is the fastest way to understand why
"find the subscriber and authenticate them" looks so different across generations.

## Who this is for

- **Students and career changers** who want a real mobile core on a laptop
  instead of diagrams.
- **SOC analysts and detection engineers** who need signalling telemetry to
  write and test rules against.
- **Telecom security researchers** who want a safe, reproducible baseline for
  explaining an attack path without needing carrier access.
- **Instructors** running a workshop: one `./up.sh` per lab, no hardware or
  radio licence required.

No telecom background is assumed. The READMEs explain each layer in plain
language and name every protocol you will meet.

## What you can do with it

- Watch a simulated 5G handset authenticate (5G-AKA) and get an IP address.
- Prove the user-plane path with a ping through `uesimtun0`, then read the
  AMF/SMF logs that produced it.
- Break registration on purpose by deleting the subscriber, then fix it.
- Capture a real SCTP association and identify `INIT`, `COOKIE` and M3UA `DATA`.
- Read MAP messages (`sendRoutingInfoForSM`, `provideSubscriberInfo`,
  `updateLocation`, `sendAuthInfo`) as both hex and named fields, validated by
  the actual 3GPP ASN.1.
- Learn a baseline from quiet traffic, then watch three detection rules catch a
  burst against one IMSI and a sweep across ten IMSIs
  (`ss7-lab/tools/detect-demo.sh`).
- Read the defensive reasoning behind it all in
  [`docs/threat-model.md`](docs/threat-model.md): how signalling access exists
  as a supply chain, why SMS OTP fails against SIM swap, and why a phone number
  cannot be treated as a secret.

## Architecture

```
5g-lab
  ue (UERANSIM) --NGAP--> gnb (UERANSIM) --N2/N3--> amf/smf/upf
                                                   |  |     |
                                            nrf scp ausf udm udr pcf nssf bsf
                                                   |
                                                mongo (subscriber DB)

ss7-lab
  map_client.py --TCP(framed)--> hlr_mock.py                (MAP/TCAP, mock transport)
  osmo-bsc  --M3UA/SCTP--> osmo-stp <--M3UA/SCTP-- osmo-msc --GSUP--> osmo-hlr
                                   |                    `--MGCP--> osmo-mgw
                                   `-- SCCP/BSSMAP (A-interface)
```

## Quickstart

Requires Docker 24+ with Compose v2, ~4 GB free RAM, and `/dev/net/tun`.

```bash
# 5G core, fake tower, fake phone
cd 5g-lab
./up.sh
docker exec -it 5glab-ue ip -br a                       # expect uesimtun0 10.45.0.2
docker exec -it 5glab-ue ping -I uesimtun0 -c3 1.1.1.1  # data path through the core
./down.sh

# SS7/MAP lab
cd ../ss7-lab
./up.sh                                                 # starts core, provisions HLR, runs MAP demo
docker compose exec -T core ./tools/status.sh
docker compose exec -T core ./tools/capture-sctp.sh     # real SCTP INIT/COOKIE/M3UA DATA on lo
./down.sh
```

Each lab has its own README with the full command reference and failure modes.

## What is real vs simulated

Being explicit about this is part of the point of the repo.

| Component | Status |
|-----------|--------|
| Open5GS NFs, UERANSIM, 5G-AKA, NAS, NGAP, PFCP, GTP-U | Real implementations, loopback Docker network |
| Osmocom M3UA/SCTP/SCCP/BSSMAP/GSUP/MGCP | Real implementations, loopback only |
| MAP operation encoding (SRISM, PSI, UpdateLocation, SendAuthInfo) | Real 3GPP ASN.1, validated with pycrate |
| MAP transport | Mock: length-prefixed TCP + TCAP Begin/End, **not** SCCP |
| MAP responder | `hlr_mock.py`, not an HLR implementation |
| Radio access | None. No BTS/SDR, so no over-the-air attach |
| Carrier connectivity | None. Every bind is `127.0.0.1` |

Two honest gaps worth knowing before you read the code:

- Osmocom's HLR speaks **GSUP**, its own MAP replacement; it does not implement
  MAP. Hence the mock.
- Neither Open5GS nor Osmocom implements 3GPP **LCS** (TS 23.271), so
  network-assisted positioning is out of scope.

## Scope and responsible use

This repository is for **defensive study, teaching, and detection engineering**.

- Everything runs on loopback or a private Docker network. There is no code
  here for reaching a carrier network, and none will be accepted.
- The MAP tooling produces standards-conformant messages and validates them
  with public 3GPP definitions (via [pycrate](https://github.com/P1sec/pycrate)).
  It has no interconnect, routing, or delivery capability.
- Do not point any of this at networks or subscribers you do not own or have
  written authorisation to test. The lab exists so you can learn the mechanism
  and then build detections against it.
- Pull requests that add real-network targeting, provider enumeration, or
  "locate a number" workflows will be rejected.

See [SECURITY.md](SECURITY.md) for reporting and the full boundary.

## Repo layout

```
mobile-network-labs/
├── 5g-lab/          # Open5GS + UERANSIM compose stack, provisioning, scripts
├── ss7-lab/         # Osmocom core, MAP/TCAP tools, audit log, detection, configs
├── docs/            # threat-model.md: access classes, SIM swap, identity resolution
├── SECURITY.md      # scope and responsible-use boundary
└── THIRD_PARTY.md   # licenses of everything pulled or derived
```

## Suggested learning path

1. Bring up `5g-lab/`, prove the data path, read the AMF log through registration.
2. Delete the subscriber, watch registration fail, re-add it.
3. Bring up `ss7-lab/`, read the four MAP operations in the demo output.
4. Capture SCTP and match the packets to the ASP states in the STP.
5. Run `ss7-lab/tools/detect-demo.sh`: quiet baseline, then a burst, then a
   sweep. Change the thresholds and re-run until you can say why each finding
   fired, and what a legitimate retry storm would do to it.
6. Change the mock's location/age values in `ss7-lab/tools/mapops.py` and watch
   the BER bytes move. Then add a fifth operation and let pycrate reject your
   tags until they are right.

Step 6 is where "ran a lab" turns into "understands the encoding". Step 5 is
where it turns into "can defend it".

## References

- 3GPP TS 29.002 — MAP
- 3GPP TS 23.040 — SMS
- 3GPP TS 23.271 — LCS (not implemented here)
- 3GPP TS 38.413 — NGAP; TS 29.244 — PFCP; TS 29.281 — GTP-U
- [Open5GS docs](https://open5gs.org/open5gs/docs/)
- [UERANSIM](https://github.com/aligungr/UERANSIM)
- [Osmocom](https://osmocom.org/) (osmo-stp, osmo-hlr, osmo-msc, osmo-bsc, osmo-mgw)
- [pycrate](https://github.com/P1sec/pycrate)

## License

MIT for this repository's code. Osmocom, pycrate, Open5GS, UERANSIM and the
container base images keep their own licenses; see
[THIRD_PARTY.md](THIRD_PARTY.md) for details, including the two Open5GS-derived
files in `5g-lab/` that remain AGPL-3.0.
