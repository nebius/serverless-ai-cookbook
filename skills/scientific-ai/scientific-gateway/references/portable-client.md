# Use the same skills without LibreChat

Install this entire versioned bundle in your agent's skill directory. Configure
the hosted Scientific AI MCP endpoint and your user API key in that client's
secret/configuration mechanism. Use the endpoint issued by your operator, not a
hard-coded example IP. Skills do not contain keys, grant models or create cloud
accounts. The model MCP's name may differ from `bionemo-models` in your client.

The portable core is caller-scoped discovery, `get_model_schema`, named model
tools and operation/batch/artifact lifecycle tools. Use their exact registered
names. The tool schema wins over every example in this bundle.

| Capability | Hosted model MCP | LibreChat workbench addition |
| --- | --- | --- |
| Typed model calls, durable IDs, polling | Yes, according to grants | Compact discovery/status wrappers |
| Artifact upload/download protocol | Yes | Workspace panel and trusted file clients |
| Local file reading / code execution | Your client must provide it | `environment-execution` and mounted workspace |
| Multi-phase study supervision | Not implied by model MCP | Existing durable study executor |
| Interactive structure display | Not implied by model MCP | Connected `structure-viewer` |
| Clinical report helpers | Bundled scripts can run locally | `scientific-demos` UI/tools and configured provider |

`/app/skill` and `/opt/bionemo` are image paths, not required paths on a customer's
laptop. Resolve this bundle's relative scripts locally. Clinical scripts include
their dependency metadata; follow their help and read credentials from configured
environment/files, never from chat. The complete hosted workbench's file clients
remain in `templates/hcls-librechat` in the same repository; downloading only
skills does not install that runtime or a supervisor.

If a tool or trusted file executor is absent, name that precise missing
capability and prepare the supported handoff. Do not claim all model calls are
impossible, invent a helper, or paste large base64/files into the model context.
Native schema fields requiring base64 must be populated by local code, not chat.
Do not send a local path as if the remote model can read it.
