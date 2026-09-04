# HCLS Workbench

One browser UI for any HCLS API v1 endpoint. Deploy compute first, then open this CPU
endpoint, sign in, select or paste the compute URL, enter its bearer token, and launch
the endpoint's guided example.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fworkbench%3A20260904-2eb701e&amp;targetPort=8000&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;diskSize=50GiB&amp;preemptible=false"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Before creating the endpoint, add `HCLS_UI_ACCESS_KEY` from a MysteryBox secret and
leave Nebius endpoint authentication disabled so a normal browser can reach the login
page. Optionally add `HCLS_DEFAULT_ENDPOINTS_JSON`; it contains URLs only, never tokens.

The workbench does no scientific compute. It discovers `/v1/capabilities`, submits and
polls runs, renders JSON results, and proxies bounded artifact downloads. Compute
tokens remain only in server process memory under an expiring HttpOnly/SameSite
session. They are never placed in browser storage, URLs, source, logs, or deployment
links.

Build from the repository root:

```bash
docker build --platform linux/amd64 \
  -f templates/hcls-workbench/Dockerfile \
  -t hcls-workbench:local .
```

Runtime settings:

| Variable | Purpose |
| --- | --- |
| `HCLS_UI_ACCESS_KEY` | Required, at least 16 characters; store as a runtime secret |
| `HCLS_DEFAULT_ENDPOINTS_JSON` | Optional list of `{name,url}` choices; never include tokens |
| `HCLS_ALLOWED_ENDPOINT_SUFFIXES` | Comma-separated managed HTTPS hostname suffixes |
| `HCLS_SESSION_TTL_SECONDS` | In-memory login/connection lifetime; default four hours |

The workbench itself uses application-level login, so its Nebius endpoint can be
browser-reachable without requiring the browser to construct an Authorization header.
Use a strong secret for `HCLS_UI_ACCESS_KEY`. Compute endpoints remain protected by
Nebius bearer-token auth.

Local browser acceptance:

```bash
docker run --rm -p 8000:8000 \
  -e HCLS_UI_ACCESS_KEY='<strong local key>' \
  -e HCLS_ALLOW_LOCAL_ENDPOINTS=1 \
  -e HCLS_COOKIE_SECURE=0 \
  hcls-workbench:local
```

Opening the UI never launches compute. All scientific outputs are explicitly marked
research-only and must be validated by the relevant domain workflow.
