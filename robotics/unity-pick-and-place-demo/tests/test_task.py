"""The artifact gate accepts a complete task and rejects fake contact/motion."""
import csv,json,sqlite3,tempfile,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check import task_measurements
def task_fixtures(root):
 root=Path(root)
 (root/'renderer.json').write_text(json.dumps({'device':'NVIDIA L40S','vendor':'NVIDIA Corporation','api':'OpenGLCore'}))
 (root/'task.json').write_text(json.dumps({'success':True,'phase':'done'}))
 (root/'policy-metadata.json').write_text(json.dumps({'sha256':'test','velocity_limit':.175}))
 phases=['approach','descend','grasp','lift','carry','lower','release','retreat','done','done']
 traces=[{'stamp':[i,0],'phase':phase,'q':[0]*6,'observation':[0]*6,'action':[.1]*6,'latency_ms':1} for i,phase in enumerate(phases)]
 (root/'policy.jsonl').write_text('\n'.join(map(json.dumps,traces)))
 (root/'perception.jsonl').write_text('\n'.join(json.dumps({'phase':'approach','red_pixels':80,'cube_estimate':[-.2,-.25,.05]}) for _ in range(2)))
 with (root/'applied.csv').open('w') as f:
  writer=csv.writer(f);writer.writerow(['time_s','observation_stamp']+[f'v{i}' for i in range(6)])
  writer.writerows([[i,i]+[.1]*6 for i in range(10)])
 rows=[[i,-.2,(-.25 if i<4 else .25),(.25 if 3<=i<6 else .05),0,1,1,phase] for i,phase in enumerate(phases)]
 write_objects(root,rows);bag=root/'rosbag';bag.mkdir();(bag/'metadata.yaml').write_text('fixture')
 with sqlite3.connect(bag/'data.db3') as db:
  db.execute('create table topics(id integer,name text)');db.execute('create table messages(topic_id integer)')
  for i,topic in enumerate(['/joint_states','/tool_pose','/joint_commands','/camera/image/compressed','/gripper_command','/gripper_contacts','/cube_ground_truth','/task_phase']):
   db.execute('insert into topics values (?,?)',(i,topic));db.executemany('insert into messages values (?)',[(i,)]*11)
 return rows


def write_objects(root,rows):
 with (root/'objects.csv').open('w') as f:
  writer=csv.writer(f);writer.writerow(['time_s','x_m','y_m','z_m','grip','left_contact','right_contact','phase']);writer.writerows(rows)


def main():
 with tempfile.TemporaryDirectory() as directory:
  root=Path(directory)
  rows=task_fixtures(root)
  assert task_measurements(root)['placement_error_m']==0
  for column,value in [(5,0),(3,.05),(2,-.25)]:
   original=[row[:] for row in rows]
   for row in rows:row[column]=value
   write_objects(root,rows)
   try:task_measurements(root)
   except ValueError:pass
   else:raise AssertionError('Accepted missing contact, lift or placement')
   rows=original
  write_objects(root,rows)
  for filename,field,value in [
   ('objects.csv','time_s','not-a-time'),('objects.csv','time_s','nan'),
   ('objects.csv','time_s','-1'),('objects.csv','grip','nan'),
   ('objects.csv','left_contact','2'),('objects.csv','x_m','inf'),
   ('applied.csv','time_s','nan'),('applied.csv','observation_stamp','inf'),
   ('applied.csv','v0','nan'),('applied.csv','v5','-inf')]:
   path=root/filename;original=path.read_text();lines=original.splitlines()
   values=lines[1].split(',');values[lines[0].split(',').index(field)]=value
   lines[1]=','.join(values);path.write_text('\n'.join(lines)+'\n')
   try:task_measurements(root)
   except ValueError:pass
   else:raise AssertionError(f'Accepted invalid {filename} {field}={value}')
   finally:path.write_text(original)
  for filename in ['objects.csv','applied.csv']:
   path=root/filename;original=path.read_text();lines=original.splitlines()
   values=lines[2].split(',');values[0]='0';lines[2]=','.join(values)
   path.write_text('\n'.join(lines)+'\n')
   try:task_measurements(root)
   except ValueError:pass
   else:raise AssertionError(f'Accepted repeated {filename} timestamp')
   finally:path.write_text(original)
  (root/'renderer.json').write_text(json.dumps({'device':'NVIDIA GeForce RTX 4090','vendor':'NVIDIA Corporation','api':'OpenGLCore'}))
  assert task_measurements(root)['renderer']['device']=='NVIDIA GeForce RTX 4090'
  commands=(root/'applied.csv').read_text()
  (root/'applied.csv').write_text(commands.replace('0.1','0.15'))
  try:task_measurements(root)
  except ValueError:pass
  else:raise AssertionError('Accepted command mismatch')
  (root/'applied.csv').write_text(commands)
  with sqlite3.connect(root/'rosbag/data.db3') as db:
   db.execute('DELETE FROM messages')
  try:task_measurements(root)
  except ValueError:pass
  else:raise AssertionError('Accepted empty ROS recording')
  with sqlite3.connect(root/'rosbag/data.db3') as db:
   db.executemany('INSERT INTO messages VALUES (?)',[(i,) for i in range(8) for _ in range(11)])
  (root/'renderer.json').write_text(json.dumps({'device':'llvmpipe','vendor':'Mesa','api':'OpenGLCore'}))
  try:task_measurements(root)
  except ValueError:pass
  else:raise AssertionError('Accepted CPU renderer')
 print('Task evidence, corrupt CSV rejection, RTX acceptance and CPU rejection passed')


if __name__ == '__main__':
 main()
