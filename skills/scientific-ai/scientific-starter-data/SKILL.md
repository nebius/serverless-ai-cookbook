---
name: scientific-starter-data
description: Find and use the customer's installed scientific starter datasets, model recipes and provenance manifest from their workspace without inventing paths or substituting demo data for a user's experiment.
license: Apache-2.0
---

# Starter data

Use `scientific-gateway` for model contracts. Discover the actual workspace root
and starter manifest with the client file tools; don't assume a historical
tenant, bucket name or seed-pack version. If absent, explain how the operator can
seed it, rather than inventing files or copying another tenant's artifacts.

Read the pack README/index and only the selected recipe. Record source/license,
pack version, input paths and hashes. Check that the caller's live catalog still
exposes the recipe's App and that its current schema matches the recipe. A
catalog addition does not guarantee a starter fixture exists yet.

For an example run, explain that these are demo/reference inputs. Preserve the
original fixtures and write outputs into a new caller-owned study directory.
Never replace user-supplied data with a fixture to obtain a passing response.
Use the durable file clients; local paths are not already-finalized artifacts.

If a reference result is included, check whether it is measured or illustrative,
and match its exact inputs/model/options before comparing. Fixture availability,
schema acceptance and scientific reproduction are three different claims.
