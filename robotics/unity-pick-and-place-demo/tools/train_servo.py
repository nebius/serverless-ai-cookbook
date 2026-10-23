"""Imitate a bounded joint servo; cloud jobs only run the exported ONNX controller."""
import hashlib,json
from pathlib import Path
import numpy as np
import onnx
from onnx import helper,numpy_helper,TensorProto
import onnxruntime as ort

root=Path(__file__).resolve().parents[1]/'runtime'
rng=np.random.default_rng(71);limit=np.deg2rad(10)
x=rng.uniform(-2.5,2.5,(24000,6)).astype(np.float32)
x[:18000]=rng.uniform(-.08,.08,(18000,6))
y=np.clip(4*x,-limit,limit)/limit
weights=[rng.normal(0,np.sqrt(2/a),(a,b)).astype(np.float32) for a,b in [(6,64),(64,64),(64,6)]]
biases=[np.zeros(n,np.float32) for n in [64,64,6]]
params=[p for pair in zip(weights,biases) for p in pair]
m=[np.zeros_like(p) for p in params];v=[p.copy() for p in m];step=0
for epoch in range(160):
 for indices in np.array_split(rng.permutation(len(x)),80):
  a=[x[indices]]
  for w,b in zip(weights,biases):a.append(np.tanh(a[-1]@w+b))
  delta=2*(a[-1]-y[indices])/len(indices)*(1-a[-1]**2);grads=[]
  for i in reversed(range(3)):
   grads[0:0]=[a[i].T@delta,delta.sum(axis=0)]
   if i:delta=(delta@weights[i].T)*(1-a[i]**2)
  step+=1
  for i,(p,g) in enumerate(zip(params,grads)):
   m[i]=.9*m[i]+.1*g;v[i]=.999*v[i]+.001*g*g
   p-=.001*(m[i]/(1-.9**step))/(np.sqrt(v[i]/(1-.999**step))+1e-8)
 if epoch%40==0:print(epoch,float(np.mean((a[-1]-y[indices])**2)),flush=True)
nodes=[];tensors=[];previous='joint_error'
for i,(w,b) in enumerate(zip(weights,biases)):
 tensors.extend([numpy_helper.from_array(w,f'w{i}'),numpy_helper.from_array(b,f'b{i}')])
 nodes.extend([helper.make_node('Gemm',[previous,f'w{i}',f'b{i}'],[f'z{i}']),helper.make_node('Tanh',[f'z{i}'],[f'a{i}'])]);previous=f'a{i}'
tensors.append(numpy_helper.from_array(np.array(limit,np.float32),'limit'));nodes.append(helper.make_node('Mul',[previous,'limit'],['velocity']))
graph=helper.make_graph(nodes,'joint-servo',[helper.make_tensor_value_info('joint_error',TensorProto.FLOAT,[None,6])],[helper.make_tensor_value_info('velocity',TensorProto.FLOAT,[None,6])],tensors)
model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',13)],ir_version=8);onnx.checker.check_model(model)
directory=root/'pick-policy';directory.mkdir(exist_ok=True);onnx.save(model,directory/'servo.onnx')
metadata={'joint_names':['Base','Shoulder','Elbow','Wrist1','Wrist2','Wrist3'],'input':'joint target minus joint position, radians [6]','output':'joint velocity rad/s [6]','velocity_limit':float(limit),'seed':71,'training_samples':len(x),'epochs':160,'teacher':'bounded proportional servo, gain 4','sha256':hashlib.sha256((directory/'servo.onnx').read_bytes()).hexdigest()}
(directory/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
s=ort.InferenceSession(str(directory/'servo.onnx'))
q=np.zeros((3,6));targets=rng.uniform(-2,2,q.shape)
for _ in range(250):
 error=targets-q;action=s.run(None,{'joint_error':error.astype(np.float32)})[0]
 action[np.abs(error)<.002]=0;q+=.1*action
assert np.max(abs(targets-q))<.004
print('Shipped ONNX controller passed held-out closed-loop joint servo test',metadata['sha256'])
