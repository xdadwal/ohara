# Public image pins

Each `PROJECT.env` contains the reviewed public image references/digests for the
matching `../compose/PROJECT.yaml`. These are literal validated manifests, not
shell scripts and not private credentials. Never put account inputs here or
source manifests. AdGuard's pin is independent of the eleven-app stack manifest.

Image updates still require upstream/architecture review and the relevant
checks. See [deployment layout](../docs/deployment-layout.md) and service guides.
