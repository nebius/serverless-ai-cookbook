"""Check camera calibration, safe IK poses and shipped learned servo."""
import hashlib,json,sys
from pathlib import Path
from io import BytesIO
import numpy as np
import onnxruntime as ort
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.perception import locate
from runtime.pick_kinematics import pose,solve,vector,S
root=Path(__file__).resolve().parents[1]/'runtime'
chain=json.loads((root/'pick-kinematics.json').read_text())
metadata=json.loads((root/'pick-policy/metadata.json').read_text())
assert hashlib.sha256((root/'pick-policy/servo.onnx').read_bytes()).hexdigest()==metadata['sha256']
assert metadata['joint_names']==[j['name'] for j in chain['joints']]
assert np.linalg.norm(pose(np.zeros(6),chain)[0]-S@vector(chain['initialTool']))<1e-5
cal={'fx':514.68,'fy':514.68,'cx':320,'cy':240,'camera_height_m':1.4,'pickup_plane_m':.05}
rgb=np.zeros((480,640,3),np.uint8);rgb[312:320,411:419,0]=255
stream=BytesIO();Image.fromarray(rgb).save(stream,format='PNG')
p,pixel=locate(stream.getvalue(),cal)
assert np.linalg.norm(p-[-.2,-.25,.05])<.003
blank=BytesIO();Image.new('RGB',(640,480)).save(blank,format='PNG');assert locate(blank.getvalue(),cal) is None
session=ort.InferenceSession(str(root/'pick-policy/servo.onnx'),providers=['CPUExecutionProvider'])
for target,seed,orientation in [([-.2,-.25,.25],[0,1,-1,0,0,0],np.diag([-1,1,-1])),
 ([ -.2,-.25,.05],[.397,.183,-.933,-1.753,1.216,.488],np.diag([-1,1,-1])),
 ([-.2,.25,.25],[2.2,.3,-1,-1.5,2.5,0],np.diag([1,-1,-1]))]:
 reference=solve(np.array(target),seed,chain,orientation)
 q=np.zeros(6)
 for _ in range(250):
  error=(reference-q+np.pi)%(2*np.pi)-np.pi
  action=session.run(None,{'joint_error':error.astype(np.float32)[None]})[0][0]
  assert np.isfinite(action).all() and abs(action).max()<=metadata['velocity_limit']+1e-6
  action[abs(error)<.002]=0;q+=action*.1
 assert np.linalg.norm(pose(q,chain)[0]-target)<.003
if len(sys.argv)>1:
 traces=[json.loads(line) for line in (Path(sys.argv[1])/'policy.jsonl').read_text().splitlines()]
 for t in traces:
  assert np.linalg.norm(pose(t['q'],chain)[0]-t['tool'])<1e-4
  a=session.run(None,{'joint_error':np.array(t['observation'],np.float32)[None]})[0][0]
  a[np.abs(t['observation'])<.002]=0
  if t['joint_target'] is not None: assert np.max(abs(a-t['action']))<1e-6
print('Camera localization, scene kinematics, learned servo and replay checks passed')
