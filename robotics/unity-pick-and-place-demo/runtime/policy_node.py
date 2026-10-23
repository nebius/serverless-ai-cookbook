"""Camera segmentation -> pose IK -> learned joint servo -> physical pick/place."""
import hashlib,json,os,time
from pathlib import Path
import numpy as np
import onnxruntime as ort
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import JointState,CompressedImage
from geometry_msgs.msg import PoseStamped,PointStamped
from trajectory_msgs.msg import JointTrajectory,JointTrajectoryPoint
from std_msgs.msg import Float64,Float64MultiArray,String
from perception import locate
from pick_kinematics import solve,pose,log_rotation,rotation


class Policy(Node):
    def __init__(self):
        super().__init__('camera_guided_pick_place')
        self.output=Path(os.environ['OUTPUT_DIR']);directory=Path('/app/policy')
        self.metadata=json.loads((directory/'metadata.json').read_text())
        digest=hashlib.sha256((directory/'servo.onnx').read_bytes()).hexdigest()
        if digest!=self.metadata['sha256']: raise ValueError('Policy checksum mismatch')
        self.session=ort.InferenceSession(str(directory/'servo.onnx'),providers=['CPUExecutionProvider'])
        self.chain=json.loads(Path('/app/pick-kinematics.json').read_text())
        self.cache={};self.last_observation=time.monotonic();self.count=0
        self.phase='locate';self.stage_started=time.monotonic();self.pick=None;self.detected=None
        self.reference=None;self.contacts=[False,False];self.calibration=None
        self.goal=None;self.orientation=np.diag([-1,1,-1]);self.grip=0.
        self.trace=(self.output/'policy.jsonl').open('w',buffering=1)
        self.vision=(self.output/'perception.jsonl').open('w',buffering=1)
        self.publisher=self.create_publisher(JointTrajectory,'/joint_commands',10)
        self.gripper=self.create_publisher(Float64,'/gripper_command',10)
        self.status=self.create_publisher(String,'/task_phase',10)
        self.target=self.create_publisher(PointStamped,'/goal',10)
        for topic,kind in [('/joint_states',JointState),('/tool_pose',PoseStamped)]:
            self.create_subscription(kind,topic,lambda msg,t=topic:self.receive(t,msg),10)
        self.create_subscription(CompressedImage,'/camera/image/compressed',self.image,10)
        self.create_subscription(Float64MultiArray,'/gripper_contacts',lambda msg:setattr(self,'contacts',[bool(x) for x in msg.data]),10)
        self.create_timer(.5,self.watchdog)
        self.get_logger().info(f'Loaded learned joint servo {digest}; camera-guided pick/place')

    def watchdog(self):
        if time.monotonic()-self.last_observation>(30 if self.count==0 else 3):raise TimeoutError('Unity observations stopped')
        if self.phase!='done' and time.monotonic()-self.stage_started>35:raise TimeoutError(f'Task stalled in {self.phase}')

    def image(self,message):
        if self.calibration is None:self.calibration=json.loads((self.output/'camera.json').read_text())
        detection=locate(message.data,self.calibration)
        if detection is None:return
        point,pixels=detection
        self.detected=point
        self.vision.write(json.dumps({'stamp':[message.header.stamp.sec,message.header.stamp.nanosec],
            'pixel':pixels[:2],'red_pixels':pixels[2],'cube_estimate':point.tolist(),'phase':self.phase})+'\n')

    def stage(self,name):
        self.phase=name;self.stage_started=time.monotonic();self.get_logger().info(f'Task: {name}')

    def plan(self,q,tool,tool_rotation):
        p=np.array(tool)
        if self.phase=='locate':
            if self.detected is None:return np.zeros(6)
            self.pick=self.detected.copy();self.goal=self.pick+[0,0,.20]
            self.reference=solve(self.goal,[0,1,-1,0,0,0],self.chain,self.orientation)
            self.stage('approach')
        reached=np.linalg.norm(p-self.goal)<.004 and np.linalg.norm(log_rotation(self.orientation@tool_rotation.T))<.035
        if self.phase=='approach' and reached:self.stage('descend')
        elif self.phase=='descend' and reached:
            self.goal[2]=max(self.pick[2],self.goal[2]-.003)
            self.reference=solve(self.goal,self.reference,self.chain,self.orientation)
            if p[2]-self.pick[2]<.004:self.grip=1.;self.stage('grasp')
        elif self.phase=='grasp' and time.monotonic()-self.stage_started>1:
            if all(self.contacts):self.stage('lift')
        elif self.phase=='lift' and reached:
            self.goal[2]=min(self.pick[2]+.20,self.goal[2]+.003)
            self.reference=solve(self.goal,self.reference,self.chain,self.orientation)
            if p[2]>self.pick[2]+.195:
                self.goal=np.array([-.20,.25,.25]);self.orientation=np.diag([1,-1,-1])
                self.reference=solve(self.goal,[2.2,.3,-1,-1.5,2.5,0],self.chain,self.orientation)
                self.stage('carry')
        elif self.phase=='carry' and reached:self.stage('lower')
        elif self.phase=='lower' and reached:
            self.goal[2]=max(.105,self.goal[2]-.003)
            self.reference=solve(self.goal,self.reference,self.chain,self.orientation)
            if p[2]<.109:self.grip=0.;self.stage('release')
        elif self.phase=='release' and time.monotonic()-self.stage_started>2:self.stage('retreat')
        elif self.phase=='retreat' and reached:
            self.goal[2]=min(.25,self.goal[2]+.003)
            self.reference=solve(self.goal,self.reference,self.chain,self.orientation)
            if p[2]>.245:self.stage('done')
        error=(self.reference-q+np.pi)%(2*np.pi)-np.pi
        action=self.session.run(None,{'joint_error':error.astype(np.float32)[None]})[0][0]
        action[np.abs(error)<.002]=0
        return action

    def receive(self,topic,message):
        stamp=(message.header.stamp.sec,message.header.stamp.nanosec)
        messages=self.cache.setdefault(stamp,{});messages[topic]=message
        if len(self.cache)>30:raise ValueError('Unsynchronized ROS observations')
        if len(messages)<2:return
        self.cache={k:v for k,v in self.cache.items() if k>stamp}
        joint=messages['/joint_states'];tool=messages['/tool_pose']
        if list(joint.name)!=self.metadata['joint_names'] or len(joint.position)!=6:raise ValueError('Joint mapping mismatch')
        q=np.array(joint.position);p=np.array([getattr(tool.pose.position,c) for c in 'xyz'])
        r=rotation({c:getattr(tool.pose.orientation,c) for c in 'xyzw'})
        if not np.isfinite(q).all() or not np.isfinite(p).all():raise ValueError('Nonfinite observation')
        expected,_=pose(q,self.chain)
        if np.linalg.norm(expected-p)>.005:raise ValueError('Grasp-centre kinematics mismatch; check scene startup and units')
        began=time.perf_counter();action=self.plan(q,p,r)
        if not np.isfinite(action).all() or np.max(abs(action))>self.metadata['velocity_limit']+1e-6:raise ValueError('Invalid learned controller output')
        command=JointTrajectory();command.header=joint.header;command.joint_names=list(joint.name)
        point=JointTrajectoryPoint();point.velocities=action.astype(float).tolist();point.time_from_start.nanosec=100000000;command.points=[point]
        self.publisher.publish(command);self.gripper.publish(Float64(data=self.grip));self.status.publish(String(data=self.phase))
        if self.goal is not None:
            goal=PointStamped();goal.header=joint.header;goal.point.x,goal.point.y,goal.point.z=self.goal;self.target.publish(goal)
        self.count+=1;self.last_observation=time.monotonic()
        error=((self.reference-q+np.pi)%(2*np.pi)-np.pi) if self.reference is not None else np.zeros(6)
        self.trace.write(json.dumps({'stamp':stamp,'q':q.tolist(),'tool':p.tolist(),'phase':self.phase,
            'joint_target':self.reference.tolist() if self.reference is not None else None,'observation':error.tolist(),
            'action':action.tolist(),'grip_command':self.grip,'contacts':self.contacts,'goal':self.goal.tolist() if self.goal is not None else None,
            'latency_ms':(time.perf_counter()-began)*1000})+'\n')

def main():
    rclpy.init();node=None
    try:node=Policy();rclpy.spin(node)
    except ExternalShutdownException:pass
    finally:
        if node:node.trace.close();node.vision.close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
