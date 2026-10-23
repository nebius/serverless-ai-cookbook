"""Locate the red cube on the calibrated pickup plane."""
from io import BytesIO
import numpy as np
from PIL import Image

def locate(data,calibration):
    rgb=np.asarray(Image.open(BytesIO(data)).convert('RGB')).astype(float)
    mask=(rgb[:,:,0]>80)&(rgb[:,:,0]>rgb[:,:,1]*1.7)&(rgb[:,:,0]>rgb[:,:,2]*1.7)
    rows,cols=np.nonzero(mask)
    if len(rows)<20: return None
    u,v=float(np.median(cols)),float(np.median(rows))
    c=calibration;depth=c['camera_height_m']-c['pickup_plane_m']
    x=(u-c['cx'])/c['fx']*depth;z=-(v-c['cy'])/c['fy']*depth
    return np.array([z,-x,c['pickup_plane_m']]),[u,v,len(rows)]
