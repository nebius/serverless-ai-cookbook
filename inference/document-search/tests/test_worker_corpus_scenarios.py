"""Optional real-corpus integration proof. Encoding is explicitly a test fixture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/job-documents"
WORKER = r'''
import hashlib,json,os,sys
from pathlib import Path
from worker.data import load_documents,manifest_digest
from worker.durable import LocalStore,RunConfig,index_documents,inspect_documents
data,output,mode=sys.argv[1:]
config=RunConfig(manifest_digest(Path(data)),"offline-fixture-not-qwen","0"*40,8,160,{"fixture":True})
documents=load_documents(Path(data));calls=0
def encode(texts):
    global calls
    calls+=len(texts)
    return [[(x+1)/256 for x in hashlib.sha256(text.encode()).digest()[:8]] for text in texts]
embedded=0
def crash(_record):
    global embedded
    embedded+=1
    if embedded==17:
        os._exit(75)
if mode=="status":
    stats=inspect_documents(documents,LocalStore(output),config)["stats"]
else:
    stats=index_documents(documents,LocalStore(output),encode,config,batch_size=16,
                          stop_after_documents=600 if mode=="600" else None,
                          after_chunk_embedded=crash if mode=="crash17" else None)
verified=inspect_documents(documents,LocalStore(output),config)["stats"]
assert verified["documents_completed"]==stats["documents_completed"]
print(json.dumps({"stats":stats,"encoded_chunks":calls}))
'''


@unittest.skipUnless((DATA / "manifest.json").is_file(), "Prepare the real corpus with scripts/prepare_job_data.py first")
class RealCorpusRecoveryTests(unittest.TestCase):
    def test_same_command_resume_and_crash_mid_document(self):
        with tempfile.TemporaryDirectory() as temp:
            def run(name, mode="full", exit_code=0):
                result = subprocess.run([sys.executable, "-c", WORKER, str(DATA), str(Path(temp)/name), mode],
                                        cwd=ROOT, capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                return json.loads(result.stdout) if result.stdout else None
            before = run("recovery","600")
            self.assertEqual(before["stats"]["documents_completed"],600)
            self.assertEqual(before["encoded_chunks"],1206)
            resumed = run("recovery","600")
            self.assertEqual(resumed["stats"]["documents_reused"],600)
            self.assertEqual(resumed["stats"]["documents_new"],400)
            self.assertEqual(resumed["encoded_chunks"],764)
            run("unfinished","crash17",75)
            crashed = run("unfinished","status")
            self.assertEqual(crashed["stats"]["documents_completed"],10)
            self.assertEqual(crashed["stats"]["chunks_saved"],15)
            partial = run("unfinished")
            self.assertEqual(partial["stats"]["documents_reused"],10)
            self.assertEqual(partial["stats"]["documents_new"],990)
            self.assertEqual(partial["stats"]["chunks_reused"],15)
            self.assertEqual(partial["encoded_chunks"],1955)
            reused = run("recovery","600")
            self.assertEqual(reused["encoded_chunks"],0)
            for item in [resumed,partial,reused]:
                self.assertTrue(item["stats"]["complete"])
                self.assertEqual(item["stats"]["chunks_saved"],1970)
            report = os.environ.get("RECOVERY_SCENARIO_REPORT")
            if report:
                Path(report).parent.mkdir(parents=True,exist_ok=True)
                Path(report).write_text(json.dumps({
                    "scope":"Offline recovery on the pinned 1,000 real passages; local files, not Object Storage or a Serverless Job",
                    "encoding":"Deterministic eight-dimensional test fixture, NOT Qwen embeddings or a performance benchmark",
                    "processes":"Each phase ran in a new Python subprocess",
                    "controlled_600":before,"same_command_resume_400":resumed,
                    "crash_mid_document":crashed,"crash_resume":partial,
                    "complete_rerun":reused},indent=2)+"\n")
