#!/usr/bin/env python3
import json, os, subprocess, sys, urllib.request, urllib.parse, pathlib, shutil

WORKSPACE_ROOT = pathlib.Path(os.environ.get("BIONEMO_WORKSPACE_ROOT", "/workspace/shared")).resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

def reply(i, result=None, error=None):
    x={"jsonrpc":"2.0","id":i}
    if error: x["error"]={"code":-32000,"message":str(error)}
    else: x["result"]=result
    print(json.dumps(x), flush=True)
def tool(name, desc, schema): return {"name":name,"description":desc,"inputSchema":schema}
schema={"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":600}},"required":["command"]}
tools=[tool("shell_exec",f"Execute a command in the owner-controlled Serverless instance. The default working directory is the writable mounted workspace {WORKSPACE_ROOT}; full package, file, download, and conversion access is available.",schema),tool("file_read","Read a UTF-8 text file from the instance.",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}),tool("file_write",f"Write UTF-8 text to a file. Use {WORKSPACE_ROOT} for durable shared work.",{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}),tool("download_file",f"Download a URL to a local path. Use {WORKSPACE_ROOT} for durable shared work.",{"type":"object","properties":{"url":{"type":"string"},"path":{"type":"string"}},"required":["url","path"]})]
for line in sys.stdin:
 try:
  q=json.loads(line); i=q.get("id"); m=q.get("method")
  if m=="initialize": reply(i,{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"bionemo-instance-admin","version":"1.0"}})
  elif m=="ping": reply(i,{})
  elif m=="notifications/initialized": continue
  elif m=="tools/list": reply(i,{"tools":tools})
  elif m=="tools/call":
   n=q["params"]["name"]; a=q["params"].get("arguments",{})
   if n=="shell_exec":
    p=subprocess.run(a["command"],shell=True,cwd=str(WORKSPACE_ROOT),capture_output=True,text=True,timeout=min(int(a.get("timeout",600)),3600)); out=(p.stdout+p.stderr)[-200000:]; val={"content":[{"type":"text","text":out}],"isError":p.returncode!=0}
   elif n=="file_read": val={"content":[{"type":"text","text":pathlib.Path(a["path"]).read_text()}]}
   elif n=="file_write": pathlib.Path(a["path"]).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(a["path"]).write_text(a["content"]); val={"content":[{"type":"text","text":"written"}]}
   elif n=="download_file": pathlib.Path(a["path"]).parent.mkdir(parents=True,exist_ok=True); urllib.request.urlretrieve(a["url"],a["path"]); val={"content":[{"type":"text","text":a["path"]}]}
   else: raise ValueError("unknown tool")
   reply(i,val)
 except Exception as e:
  if q.get("id") is not None: reply(q.get("id"),error=e)
