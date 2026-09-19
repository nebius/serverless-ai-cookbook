# Exact endpoint reconciliation

A ten-user private-network test deployment encountered a provider `Internal`
response while creating one endpoint. The project then contained more than
the high-level CLI's first 100 list entries. Passing a page token through its
generic input-file option repeated the first page; that output did not establish
whether the named endpoint existed.

Deployment reconciliation now uses the supported project-scoped
`ai endpoint get-by-name` command and validates the exact name, project, image
and nonempty resource ID before reuse. A missing result or any lookup error
still stops for operator reconciliation: this change does not retry creation,
raise limits, delete endpoints or mutate identities.

For this particular failed test create, two explicit exact-name lookups returned
NotFound. Root retained the original failed-create and lookup receipts before
authorizing one deliberate create with the same owner, key, bucket, image and
limits. This does not explain the provider Internal error or establish an
application/runtime fault.

29 no-cloud deployment/networking tests pass, including eight added lookup
cases: exact lookup (not list), wrong name/project/image, missing ID, and
NotFound/Internal/Unauthenticated without a second creation attempt.
Protected JUnit receipt `scientific-unattended-20260919/endpoint-reconcile-source-tests-r1.xml`:
SHA256 `93a0803b82ca5baa168733092401c98786e4bca8109b7e97eb88a8a90d4f7ea8`.
These are deployment-source tests, not installed-application qualification.
