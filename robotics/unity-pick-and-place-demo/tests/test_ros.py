"""Run inside the image: check ROS observation contracts and deserialize bags."""
import os,tempfile,time
import numpy as np
import rclpy
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from policy_node import Policy
from pick_kinematics import pose
rclpy.init()
with tempfile.TemporaryDirectory() as directory:
 os.environ['OUTPUT_DIR']=directory
 node=Policy()
 def feed(names):
  joint=JointState();joint.name=names;joint.position=[0.]*6;joint.header.frame_id='base_link'
  tool=PoseStamped();tool.header=joint.header
  p,r=pose(np.zeros(6),node.chain)
  tool.pose.position.x,tool.pose.position.y,tool.pose.position.z=p
  tool.pose.orientation.x=-.70710678;tool.pose.orientation.w=.70710678
  node.receive('/joint_states',joint);node.receive('/tool_pose',tool)
 feed(node.metadata['joint_names']);assert node.count==1
 try:feed(list(reversed(node.metadata['joint_names'])))
 except ValueError as e:assert 'Joint mapping' in str(e)
 else:raise AssertionError('Wrong joint order accepted')
 node.last_observation=time.monotonic()-4
 try:node.watchdog()
 except TimeoutError:pass
 else:raise AssertionError('Stale observations accepted')
 node.trace.close();node.vision.close();node.destroy_node()
rclpy.shutdown()
print('ROS observations, joint order and watchdog checks passed')
if os.environ.get('BAG_PATH'):
 import rosbag2_py
 from rclpy.serialization import deserialize_message
 from rosidl_runtime_py.utilities import get_message
 reader=rosbag2_py.SequentialReader()
 reader.open(rosbag2_py.StorageOptions(uri=os.environ['BAG_PATH'],storage_id='sqlite3'),rosbag2_py.ConverterOptions('',''))
 types={t.name:get_message(t.type) for t in reader.get_all_topics_and_types()};counts={}
 while reader.has_next():
  topic,data,stamp=reader.read_next();message=deserialize_message(data,types[topic])
  if hasattr(message,'header'):assert message.header.frame_id=='base_link'
  counts[topic]=counts.get(topic,0)+1
 assert all(counts.get(t,0)>10 for t in ['/joint_states','/tool_pose','/camera/image/compressed','/joint_commands','/gripper_command','/cube_ground_truth'])
 print('Every ROS recording message deserialized:',counts)
