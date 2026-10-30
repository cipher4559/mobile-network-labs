# ss7-lab — SCCP/M3UA + MAP/TCAP study lab (loopback only)

> Lab-only, loopback-only. The MAP transport is a mock and nothing here can
> reach a carrier network. See the repository-level `SECURITY.md`.

Two stages that run in one container on `127.0.0.1`:

1. **Osmocom core (real protocols):** `osmo-stp`, `osmo-hlr`, `osmo-msc`,
   `osmo-bsc`, `osmo-mgw`. M3UA over SCTP (`:2905`), SCCP, BSSMAP/A-interface,
   GSUP (`:4222`) and MGCP (`:2427`) are genuine implementations.
2. **MAP/TCAP (emulated transport, real ASN.1):** `tools/hlr_mock.py` speaks
   TCAP `Begin`/`End` + MAP operations over a 4-byte length-prefixed TCP
   dialgue; every PDU is decoded/validated with the actual 3GPP ASN.1 from
   `pycrate` (`TS29002_MAPAppCtx`).

Nothing here talks to a carrier network. All binds are `127.0.0.1`.

## Run

```sh
./up.sh        # build/start core, provision subscriber, run MAP demo
./down.sh      # stop
docker compose exec -T core ./tools/status.sh
docker compose exec -T core ./tools/capture-sctp.sh   # tcpdump lo, bounces MSC
```

Reset the subscriber DB: `rm -f run/hlr.db` (then `./up.sh`).

## Ports (inside the container)

| Port | Proto | Service |
|------|-------|---------|
| 2905 | SCTP  | OsmoSTP M3UA (dynamic ASP registration) |
| 29118| SCTP  | osmo-bsc IPA/SCTP (unused without a BTS) |
| 4222 | TCP   | OsmoHLR GSUP |
| 2427 | UDP   | OsmoMGW MGCP |
| 4239/4258/4254/4243/4242 | TCP | VTY: stp/hlr/msc/mgw/bsc |

## What the demo proves

```
map_client.py --TCP--> hlr_mock.py
  Begin  + Invoke op 45  sendRoutingInfoForSM   -> imsi + networkNode-Number
  Begin  + Invoke op 70  provideSubscriberInfo  -> ageOfLocationInformation + vlr-number
  Begin  + Invoke op 2   updateLocation         -> hlr-Number
  Begin  + Invoke op 56  sendAuthInfo           -> ReturnError (systemFailure)
```

Every request/response is also checked by `pycrate`, so the tags/encodings
match real MAP, not a hand-rolled guess:

* SRISM arg `[0] msisdn, [1] sm-RP-PRI, [2] serviceCentreAddress`
* SRISM res `imsi` (untagged) + `locationInfoWithLMSI [0] -> networkNode-Number [1]`
* UpdateLocation arg `imsi` (untagged), `msc-Number [1]`, `vlr-Number` (untagged)
* ProvideSubscriberInfo arg `imsi [0]`, `requestedInfo [2] -> locationInformation [0] (NULL)`
* ProvideSubscriberInfo res `subscriberInfo -> locationInformation -> age (int) + vlr-number [1]`

Osmocom side, verified by capture and VTY:

* `show cs7 instance 0 asp` → two `ASP_ACTIVE` M3UA ASPs (MSC `0.23.1`,
  BSC `0.23.4`) registered dynamically at the STP.
* `tcpdump -i lo sctp` shows `INIT / INIT ACK / COOKIE ECHO / DATA [PPID M3UA]`.
* BSC log: `BSSMAP assocation is up` — a real SCCP/BSSMAP association
  BSC→STP→MSC.
* HLR subscriber created with 2G `COMP128v1` and 3G `MILENAGE` (same K/OPC as
  the 5G lab's `999700000000001`).

## Honest limits

* **OsmoHLR is GSUP-only.** It does not speak MAP; there is no
  `sendRoutingInfoForSM` implementation in Osmocom. The MAP layer is therefore
  a mock driven by pycrate, and its transport is TCP, not SCCP/TCAP.
* **No LCS.** Neither Osmocom nor Open5GS implements 3GPP LCS (TS 23.271), so
  "locate by MSISDN" is out of scope by design; PSI only reports what a VLR
  would report (age + VLR number).
* **No radio.** There is no BTS/SDR, so no real `Location Updating` over Um;
  the BSC's A-interface and GSUP are exercised at the signalling layer only.
* `sendAuthInfo` result encoding (triplet/quintuplet CHOICE) is left as a
  `ReturnError`; the argument side is validated.
* `osmo-stp` reports `ASP Restart for server not implemented yet` — cosmetic,
  ASPs still reach `ASP_ACTIVE`.
