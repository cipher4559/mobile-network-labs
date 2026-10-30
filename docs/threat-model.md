# Threat model — mobile signalling, SIM swap, and identity resolution

This document explains **why** the labs look the way they do. It is written for
defenders: students, SOC analysts, detection engineers, and telecom security
researchers who need to reason about mobile networks without touching one.

It describes classes of attack and the controls that matter. It does **not**
describe how to obtain signalling access, how to target a person, or how to buy
anything used to commit fraud. That boundary is deliberate and is enforced in
[`SECURITY.md`](../SECURITY.md).

---

## 1. There is no "SS7 login"

SS7/MAP has no accounts and no authentication of its own. Access exists only as
a **trust relationship between networks**: a point code, a route, and a peer
that is expected to send certain queries. Anyone who can send a query is, by
construction, trusted by whoever accepted it.

So the attacker's question is never "how do I connect to SS7" but "whose
connection can I use, or borrow, or become". The documented classes:

| Access class | Legitimate purpose | Abuse pattern | Primary control |
|---|---|---|---|
| MNO interconnect | Deliver calls/SMS to another carrier | Complicit or compromised peer sends queries it should filter | Per-service allow-lists tied to the interconnect agreement; SS7 firewall |
| Roaming / IPX hub | Route roaming traffic between operators | Hub forwards a query from an operator with no roaming relationship to the target | Home-routing for SMS; hub-level filtering; roaming-agreement-aware rules |
| SMS aggregator (A2P) | Businesses send OTP and bulk SMS | Aggregator with weak KYC resells reach; grey routes bypass agreed pricing/filtering | KYC on senders, sender-ID registration, route auditing |
| Hosted core / MVNO enabler | Small operator rents core + signalling | Tenant escape, stale credentials, former staff | Tenant isolation, credential rotation, access review |
| Test / roaming-partner account | Roaming tests, fraud analytics, interconnect acceptance | Account shared, resold, or never deprovisioned | Named accounts, expiry, query logging with a named owner |
| Insider | NOC, fraud, engineering | Bribe, coercion, curiosity, revenge | Least privilege, separation of duties, anomaly alerts on employee queries |

Two consequences follow, and they are the core lesson of the `ss7-lab`:

1. **Identity of the sender is not evidence of legitimacy.** A query arrives
   from a valid peer, with a valid point code, in a valid format.
2. **The messages are identical** to legitimate traffic. `sendRoutingInfoForSM`
   from a roaming partner and from an attacker are the same bytes. Detection is
   therefore statistical and contextual: rate, breadth, mix of operations,
   time of day, origin, and whether that origin has a *reason* to ask about that
   subscriber.

### What the industry actually does about it

- **GSMA FS.11** (interconnect security) defines the abuse categories —
  subscriber-information disclosure, location tracking, interception, SMS
  interception, fraud, denial of service — and the controls: per-service
  filtering, roaming-agreement allow-lists, and monitoring.
- **SMS home routing** keeps the SMS delivery query inside the home network, so
  an outside party cannot ask "where should I deliver this" about your
  subscriber.
- **SS7 firewalls** enforce "is this peer allowed to ask *this* question about
  *this* range", not just "is this peer allowed to connect".
- **Audit** of every interconnect query, with a named owner per account, is what
  turns the table above from a list of risks into a list of rules.

### Detection value in this lab

`tools/hlr_mock.py` writes a JSON-lines audit record per invoke: timestamp,
source, operation, and the resolved IMSI (including for `sendRoutingInfoForSM`,
which arrives with an MSISDN and leaves with an IMSI — a real resolution step an
attacker exploits and a defender can log). `tools/query_monitor.py` applies
three rules over a sliding window:

| Rule | Fires when | Maps to |
|---|---|---|
| `imsi-burst` | One IMSI receives many operations in the window (MEDIUM ≥ 6, HIGH ≥ 12 by default) | Repeated location/profile queries for one subscriber |
| `imsi-profile` | One IMSI receives ≥ 3 distinct operations in the window | The locate → profile → authenticate sequence (`SRISM`/`PSI`/`SAI`) |
| `imsi-sweep` | One source touches many distinct IMSIs (MEDIUM ≥ 4, HIGH ≥ 8) | Subscriber enumeration |

Run `tools/detect-demo.sh`: it learns a baseline from one legitimate dialogue,
then shows a burst and a sweep against the same monitor. Two honest caveats:

- **A legitimate retry storm looks like a burst.** Roaming attach, SMS retries,
  and a handset in a bad coverage area all produce repeats. Real deployments
  scope the rule by origin, by operation, and by whether the rate is abnormal
  *for that subscriber*, not just abnormal in absolute terms.
- **Rate rules alone are not FS.11 compliance.** They catch the noisy attacker.
  The quiet one — one query per day, from an origin with a plausible roaming
  agreement — is caught by agreement-based allow-lists, not by thresholds.

---

## 2. Identity resolution: the number is a public key

Before any of the above can be used, an attacker needs to turn a person into an
identifier the network understands. That step is a service, not a hack:

- **MSISDN → IMSI** is exactly what `sendRoutingInfoForSM` and `sendIMSI` do.
- **Number → name/address** is sold by data brokers ("phone append"), leaked in
  breaches, crowdsourced by caller-ID apps that upload address books, and
  published by people themselves.
- **Number portability** databases are queryable by design.

You cannot make a phone number secret. That is why the right control is
architectural: **do not use the number as an authenticator**. A number that is
public by construction must not be the thing that proves who you are.

### On "free" people-search tooling

The request "which site gives me someone's data for free" has an uncomfortable
answer: the free ones are aggregators of the above (often violating their own
terms), scam fronts, or malware. Breach corpora are **stolen data**; obtaining
or possessing them is a criminal offence in most jurisdictions and a common
infection vector. Legitimate open-source frameworks (theHarvester, SpiderFoot,
Maltego CE, Sherlock) aggregate *public* sources and are used in authorised
assessments — they do not defeat privacy controls, and using them against a
person without authorisation is where the legal exposure starts.

Defensive, self-service and free: Have I Been Pwned, Google "Results about you",
data-broker opt-out lists (and California's DROP mechanism under the Delete
Act), free credit freezes, and removing your number from public profiles.

---

## 3. SIM swap

SIM swap is **not** a signalling attack. It is account takeover at the carrier,
executed through people and process. Conflating the two is the most common
mistake in mobile threat discussions.

**Shape of the attack.** The attacker persuades the carrier to move the victim's
number onto a SIM they control — a port-out to another carrier, or a
replacement SIM/eSIM at a store or over the phone. The usual enablers are an
insider, a deceived retail agent, a weak identity check, or abuse of a
self-service port/eSIM flow. Reported cases (FCC, Ofcom, FBI IC3) consistently
show the failure is **authentication of the person, not the network**.

**Why it works.** SMS OTP treats possession of the number as proof of identity.
After the port, every SMS-based factor — bank OTP, password reset, email
recovery — lands with the attacker. NIST SP 800-63B has restricted SMS as an
authenticator for years for this reason.

**Controls that move the needle**

- Carrier side: port freeze / number lock (FCC rules adopted 2023–2024 in the
  US; Ofcom general conditions in the UK), a port-out PIN, a non-guessable
  account PIN, in-person-only changes, and eSIM transfer locks.
- Account side: move off SMS — TOTP, passkeys/FIDO2, app push with number
  matching; remove the phone number as an email-recovery path.
- Monitoring: alert on SIM change / port request; treat an unexpected "no
  service" as a security event, not a coverage problem.
- Response: contact the carrier, freeze credit (free at the three US bureaus),
  rotate passwords starting with email, and treat the number as permanently
  unusable for authentication.

**Why it belongs next to an SS7 lab.** Both attacks end with "the attacker
receives the OTP". One gets there by borrowing the network's trust, the other
by borrowing the carrier's trust in a human. Defending the account requires
assuming either can fail.

---

## 4. What this repository deliberately excludes

- No method for obtaining, leasing, or reselling signalling access; no vendors,
  brokers, or prices for grey routes.
- No phone-number → person resolution workflow, and no list of lookup services
  aimed at individuals.
- No social-engineering scripts, pretexts, or impersonation guidance.
- No live-network targets, no carrier addresses, no real subscriber data.

If you are researching this area, the useful direction is detection: telemetry
you can generate yourself, rules you can test, and controls you can verify.

---

## References

- GSMA **FS.11** Interconnect Security and **FS.19** Diameter/SS7 security
  guidelines.
- ENISA, *Signalling security in telecom SS7/Diameter/5G* (2017) — threat
  taxonomy and countermeasures.
- NIST **SP 800-63B**, *Digital Identity Guidelines* — restrictions on SMS as an
  authenticator.
- FCC rulemakings on SIM swapping and port-out protection (2023–2024); Ofcom
  general conditions on mobile number porting (2023).
- Public analyses of SS7 abuse by Citizen Lab, Google TAG, and operator fraud
  teams; the 2014 Positive Technologies location-tracking demonstration and the
  2017 Telefónica Germany incident are the commonly cited case studies.
