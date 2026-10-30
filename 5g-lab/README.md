# 5g-lab — Open5GS core + UERANSIM on one machine

A complete, no-radio 5G network in Docker: a simulated handset and base station
attach to a real open-source 5G core over a fake test PLMN, authenticate with
5G-AKA, get an IP address, and reach the internet through the core's user-plane
gateway.

```
┌────────────┐  NGAP/NAS   ┌────────────┐   N2   ┌──────────┐
│ ue         │────────────▶│ gnb        │───────▶│ amf      │
│ (UERANSIM) │  10.45.0.2  │ (UERANSIM) │        └────┬─────┘
└─────┬──────┘             └─────┬──────┘             │ SBI (HTTP/2)
      │ N3 / GTP-U               │                    ▼
      └──────────────▶ ┌──────────┴───┐        nrf scp ausf udm udr
                       │ upf          │        pcf nssf bsf
                       │ ogstun + NAT │
                       └──────────────┘
                                ▲
                            smf │ PFCP
                                │
                        ┌───────┴────────┐
                        │ mongo          │  subscriber database
                        └────────────────┘
```

## Requirements

- Docker with Compose v2
- ~4 GB free RAM
- `/dev/net/tun` available on the host
- outbound internet for image pulls

## Quickstart

```bash
./up.sh        # mongo -> core NFs -> provision subscriber -> gNB -> UE
docker compose ps
```

Verify the phone attached and data flows:

```bash
docker exec -it 5glab-ue ip -br a
# expect: uesimtun0  UNKNOWN  10.45.0.2/16

docker exec -it 5glab-ue ping -I uesimtun0 -c3 10.45.0.1   # core gateway
docker exec -it 5glab-ue ping -I uesimtun0 -c3 1.1.1.1     # out to the internet
```

`-I uesimtun0` matters: without it, ping leaves via the container's normal
Docker network and proves nothing about the mobile data path.

Watch the control plane:

```bash
docker compose logs -f amf     # authentication / registration
docker compose logs -f smf     # session creation, UE IP assignment
```

Tear down:

```bash
./down.sh        # keep the subscriber database
./down.sh -v     # wipe it; the next up.sh starts clean
```

## Subscriber

Provisioned by `./provision.sh` (idempotent: delete + add):

| Field | Value |
|-------|-------|
| IMSI | `999700000000001` |
| PLMN | MCC `999`, MNC `70` (test network) |
| TAC | `1` |
| Slice | SST `1`, SD `000001` |
| DNN / APN | `internet` |
| K | `465B5CE8B199B49FAA5F0A2EE238A6BC` |
| OPC | `E8ED2A9CDFB6DFC9E1E6B4B0A5C1D9E2` |

After changing subscriber data, restart the caches so the change is visible:

```bash
docker compose restart udr udm amf
```

### Experiment: make registration fail

```bash
docker exec -it 5glab-mongo mongosh --quiet open5gs --eval \
  'db.subscribers.deleteOne({imsi:"999700000000001"})'
docker compose restart udr udm amf
docker compose restart ue
docker compose logs -f amf      # watch the registration reject
./provision.sh && docker compose restart udr udm amf ue
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 14 services: mongo, 11 NFs, gNB, UE; healthcheck + restart policies |
| `up.sh` | Ordered cold start (mongo healthy -> NFs -> provision -> gNB -> UE) |
| `down.sh` | `docker compose down "$@"` |
| `provision.sh` | Subscriber insert via `mongosh` |
| `amf.yaml` | Patched AMF config (mounted read-only) |
| `smf-fd.conf` | Patched SMF freeDiameter config (mounted read-only) |
| `upf-entry.sh` | Creates `ogstun`, adds the UE subnet route, enables NAT, execs `open5gs-upfd` |
| `open5gs-dbctl` | Upstream provisioning helper |

## Known gotchas (already fixed here)

These are the failure modes that cost the most time when building this, kept
because they are instructive:

1. **AMF needs the slice SD.** Without `plmn_support[].s_nssai.sd: 000001`,
   registration fails even though the subscriber has the slice.
2. **`slice.0.sd` must be a string.** If it is stored as a number, the SMF/UDM
   comparison fails. `provision.sh` writes `"000001"`.
3. **SMF's freeDiameter peer is dead weight.** `ConnectPeer = "pcrf.gradiant"`
   in `smf-fd.conf` makes SMF abort; it is commented out in the mounted copy.
4. **UPF and UE need privileges.** The images run as `open5gs`, so both need
   `user: "0:0"`, `NET_ADMIN`, and `/dev/net/tun` to create `ogstun`/`uesimtun0`.
5. **Cold-start races.** Mongo must be healthy before UDR/PCF; SMF must wait for
   UPF (with UPF not waiting on SMF, or the dependency is circular).
6. **`down -v` deletes the subscriber database**, not just containers.

## Limits

- No radio hardware: UERANSIM simulates both the UE and the gNB, so there is no
  over-the-air attach and no RF to analyse.
- Single PLMN, single subscriber, no roaming, no policy/charging depth.
- NGAP, PFCP and GTP-U are exercised, but this is not a performance or
  conformance testbed.
