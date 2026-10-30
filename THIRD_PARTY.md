# Third-party components

The MIT license at the root of this repository covers the code written for this
project. The components below are **not** MIT; they are pulled, installed, or
derived from upstream projects and keep their own licenses.

## 5g-lab

| Component | License | How it appears here |
|-----------|---------|---------------------|
| [Open5GS](https://github.com/open5gs/open5gs) | AGPL-3.0 | Container images (`gradiant/open5gs:2.8.0`); `5g-lab/open5gs-dbctl` copied unmodified for provisioning; `5g-lab/amf.yaml` and `5g-lab/smf-fd.conf` are modified copies of upstream sample configs |
| [UERANSIM](https://github.com/aligungr/UERANSIM) | GPL-3.0 | Container images (`gradiant/ueransim:3.3.0`); no source vendored |
| [MongoDB](https://www.mongodb.com/) | SSPL | Container image (`mongo:7`); no source vendored |

`open5gs-dbctl` retains its upstream provenance; because it is distributed here
verbatim, its AGPL-3.0 terms apply to that file. The two config files are
derived from upstream samples and carry the same license. The upstream source
is available at the links above.

## ss7-lab

| Component | License | How it appears here |
|-----------|---------|---------------------|
| [Osmocom](https://osmocom.org/) — osmo-stp, osmo-hlr, osmo-msc, osmo-bsc, osmo-mgw | GPL-2.0 / AGPL-3.0 (varies by program) | Installed as Debian packages in the image; no source vendored. The `ss7-lab/conf/*.cfg` files are written for this lab, based on the packages' default configuration |
| [pycrate](https://github.com/P1sec/pycrate) | LGPL-3.0 | `pip install pycrate==0.8.1` at image build time; no source vendored |
| Debian 12 (slim) | mixed DFSG-free | Base image |

## Note on distribution

This repository does not redistribute any of the above as source. It builds a
Docker image that installs them from their official distribution channels
(Debian archives, PyPI) and references public container images. If you fork or
redistribute a built image, review the upstream licenses — in particular
AGPL-3.0 for Open5GS and parts of Osmocom, which impose source-availability
obligations on network-served modified versions.
