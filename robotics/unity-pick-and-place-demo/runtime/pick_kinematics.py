"""Scene-derived grasp-centre kinematics and pose IK; Unity RUF -> ROS FLU."""
import json
import numpy as np

S=np.array([[0,0,1],[-1,0,0],[0,1,0]])
def vector(v): return np.array([v[c] for c in 'xyz'])
def rotation(v):
    x,y,z,w=[v[c] for c in 'xyzw']
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def pose(q,chain):
    r=np.eye(3); p=np.zeros(3)
    for angle,j in zip(q,chain['joints']):
        p+=r@vector(j['parentPosition']);r=r@rotation(j['parentRotation'])
        c,s=np.cos(angle),np.sin(angle)
        r=r@np.array([[1,0,0],[0,c,-s],[0,s,c]])@rotation(j['childRotation']).T
        p-=r@vector(j['childPosition'])
    p+=r@vector(chain['tip']);r=r@rotation(chain['tipRotation'])
    return S@p,S@r@S.T

def log_rotation(r):
    angle=np.arccos(np.clip((np.trace(r)-1)/2,-1,1))
    if angle<1e-6:return np.zeros(3)
    if abs(np.sin(angle))<1e-5:
        vals,vecs=np.linalg.eig(r);axis=np.real(vecs[:,np.argmin(abs(vals-1))]);return axis*angle
    return np.array([r[2,1]-r[1,2],r[0,2]-r[2,0],r[1,0]-r[0,1]])*(angle/(2*np.sin(angle)))

def solve(target,q,chain,orientation=np.diag([-1,1,-1])):
    q=np.array(q,float).copy(); scale=np.array([1,1,1,.25,.25,.25])
    for _ in range(180):
        p,r=pose(q,chain);error=np.r_[target-p,log_rotation(orientation@r.T)]
        if np.linalg.norm(error[:3])<.001 and np.linalg.norm(error[3:])<.01:return q
        jac=[]
        for i in range(6):
            offset=np.eye(6)[i]*1e-4;p1,r1=pose(q+offset,chain)
            jac.append(np.r_[(p1-p)/1e-4,log_rotation(r1@r.T)/1e-4])
        j=np.array(jac).T*scale[:,None]
        step=j.T@np.linalg.solve(j@j.T+np.eye(6)*.0002,error*scale)
        q+=np.clip(step,-.15,.15)
        q=(q+np.pi)%(2*np.pi)-np.pi
    raise ValueError(f'IK could not reach position/orientation: {target.tolist()}')
