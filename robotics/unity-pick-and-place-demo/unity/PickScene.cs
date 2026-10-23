using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using RosMessageTypes.Sensor;
using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;

public partial class DemoRun {
    Rigidbody block;
    BlockContacts contacts;
    Camera perceptionCamera;
    RenderTexture visionTarget;
    Texture2D visionPixels;
    StreamWriter objects;
    float nextVision, highestBlock, completedAt=-1;
    string phase="locate";
    bool graspContact;
    readonly Vector3 destination=new Vector3(-.25f,.05f,-.20f);

    void PreparePickScene() {
        block=GameObject.Find("Cube").GetComponent<Rigidbody>();
        block.transform.localScale=Vector3.one*.04f;
        block.transform.position=robot.transform.TransformPoint(new Vector3(.25f,.065f,-.20f));
        block.transform.rotation=Quaternion.identity;
        block.mass=.05f; block.useGravity=true; block.isKinematic=false;
        block.collisionDetectionMode=CollisionDetectionMode.ContinuousDynamic;
        block.solverIterations=32; block.solverVelocityIterations=16;
        block.GetComponent<Renderer>().material.color=new Color(1,.03f,.03f);
        var friction=new PhysicsMaterial("Grasp friction") { dynamicFriction=1,staticFriction=1,bounciness=0,
            frictionCombine=PhysicsMaterialCombine.Maximum,bounceCombine=PhysicsMaterialCombine.Minimum };
        block.GetComponent<Collider>().material=friction;
        foreach(var finger in new[] {gripper.fingerA,gripper.fingerB}) {
            finger.GetComponent<Collider>().material=friction;
            var body=finger.GetComponent<ArticulationBody>();
            var drive=body.zDrive; drive.stiffness=3000; drive.damping=80; drive.forceLimit=20; body.zDrive=drive;
        }
        contacts=block.gameObject.AddComponent<BlockContacts>();
        contacts.left=gripper.fingerA.GetComponent<Collider>(); contacts.right=gripper.fingerB.GetComponent<Collider>();
        Pad("Pickup pedestal",new Vector3(.25f,.015f,-.20f),new Vector3(.025f,.03f,.025f),Color.gray);
        Pad("Destination tray",new Vector3(-.25f,.015f,-.20f),new Vector3(.11f,.03f,.11f),new Color(.05f,.3f,1));
        foreach(float sign in new[] {-1f,1f}) {
            Pad("Tray wall",new Vector3(-.25f+sign*.055f,.05f,-.20f),new Vector3(.008f,.04f,.11f),Color.blue);
            Pad("Tray wall",new Vector3(-.25f,.05f,-.20f+sign*.055f),new Vector3(.11f,.04f,.008f),Color.blue);
        }
        cameraView.transform.position=robot.transform.TransformPoint(new Vector3(-.85f,.7f,-1.25f));
        cameraView.transform.LookAt(robot.transform.TransformPoint(new Vector3(0,.30f,-.08f)));
        cameraView.fieldOfView=45;
        cameraView.clearFlags=CameraClearFlags.SolidColor;cameraView.backgroundColor=new Color(.12f,.15f,.19f);
        var fill=new GameObject("Camera fill light").AddComponent<Light>();
        fill.type=LightType.Directional;fill.intensity=.8f;fill.shadows=LightShadows.None;
        fill.transform.rotation=cameraView.transform.rotation;
        RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight=new Color(.35f,.35f,.35f);
        perceptionCamera=new GameObject("Overhead perception camera").AddComponent<Camera>();
        perceptionCamera.enabled=false; perceptionCamera.fieldOfView=50;
        perceptionCamera.nearClipPlane=.01f; perceptionCamera.farClipPlane=5;
        perceptionCamera.transform.position=robot.transform.TransformPoint(new Vector3(0,1.4f,0));
        perceptionCamera.transform.rotation=robot.transform.rotation*Quaternion.LookRotation(Vector3.down,Vector3.forward);
        visionTarget=new RenderTexture(640,480,24);visionTarget.Create();
        visionPixels=new Texture2D(640,480,TextureFormat.RGB24,false);
        double fy=480/(2*Math.Tan(25*Math.PI/180));
        File.WriteAllText(Path.Combine(output,"camera.json"),"{\"width\":640,\"height\":480,\"fx\":"+Number(fy)+",\"fy\":"+Number(fy)+",\"cx\":320,\"cy\":240,\"camera_height_m\":1.4,\"pickup_plane_m\":0.05}");
        objects=new StreamWriter(Path.Combine(output,"objects.csv"));
        objects.WriteLine("time_s,x_m,y_m,z_m,grip,left_contact,right_contact,phase");
    }
    void Pad(string name,Vector3 position,Vector3 scale,Color color) {
        var obj=GameObject.CreatePrimitive(PrimitiveType.Cube);obj.name=name;
        obj.transform.SetParent(robot.transform,false);obj.transform.localPosition=position;obj.transform.localScale=scale;
        obj.GetComponent<Renderer>().material.color=color;
    }
    void RegisterPickTopics() {
        ros.RegisterPublisher<PoseStampedMsg>("/tool_pose");
        ros.RegisterPublisher<PointStampedMsg>("/cube_ground_truth");
        ros.RegisterPublisher<Float64MultiArrayMsg>("/gripper_contacts");
        ros.RegisterPublisher<CompressedImageMsg>("/camera/image/compressed");
        ros.Subscribe<Float64Msg>("/gripper_command",msg=> {
            if(!double.IsFinite(msg.data)||msg.data<0||msg.data>1) { Fail(new Exception("Gripper command must be 0..1"));return; }
            gripper.grip=(float)msg.data;gripper.gripState=GripState.Fixed;
        });
        ros.Subscribe<StringMsg>("/task_phase",msg=>phase=msg.data);
    }
    void PublishPick(RosMessageTypes.Std.HeaderMsg header,float elapsed) {
        if(phase=="done" && completedAt<0) completedAt=elapsed;
        Vector3 position=robot.transform.InverseTransformPoint(block.position);
        highestBlock=Math.Max(highestBlock,position.y);
        graspContact|=contacts.HasLeft&&contacts.HasRight;
        ros.Publish("/tool_pose",new PoseStampedMsg(header,new PoseMsg(ToROS(Tool()),
            (Quaternion.Inverse(robot.transform.rotation)*gripper.transform.rotation).To<FLU>())));
        ros.Publish("/cube_ground_truth",new PointStampedMsg(header,ToROS(position)));
        ros.Publish("/gripper_contacts",new Float64MultiArrayMsg { data=new double[] {contacts.HasLeft?1:0,contacts.HasRight?1:0} });
        if(started>0) {
            var p=ToROS(position);
            objects.WriteLine(Number(elapsed)+","+Number(p.x)+","+Number(p.y)+","+Number(p.z)+","+Number(gripper.CurrentGrip())+","+(contacts.HasLeft?1:0)+","+(contacts.HasRight?1:0)+","+phase);objects.Flush();
        }
    }
    void PublishVision(RosMessageTypes.Std.HeaderMsg header,float now) {
        if(now<nextVision) return;
        perceptionCamera.targetTexture=visionTarget;perceptionCamera.Render();RenderTexture.active=visionTarget;
        visionPixels.ReadPixels(new Rect(0,0,640,480),0,0);visionPixels.Apply();RenderTexture.active=null;perceptionCamera.targetTexture=null;
        // EncodeToPNG produces standard top-left PNG image coordinates.
        ros.Publish("/camera/image/compressed",new CompressedImageMsg(header,"png",visionPixels.EncodeToPNG()));
        nextVision=Math.Max(nextVision+.2f,now);
    }
    void FinishPick() {
        Vector3 p=robot.transform.InverseTransformPoint(block.position);
        bool placed=new Vector2(p.x-destination.x,p.z-destination.z).magnitude<.04f && Math.Abs(p.y-destination.y)<.025f;
        bool passed=phase=="done"&&placed&&highestBlock>.15f&&graspContact&&gripper.CurrentGrip()<.1f;
        File.WriteAllText(Path.Combine(output,"task.json"),"{\"success\":"+(passed?"true":"false")+",\"phase\":\""+phase+"\",\"lift_height_m\":"+Number(highestBlock)+",\"both_fingers_contacted\":"+(graspContact?"true":"false")+",\"placement_error_m\":"+Number(Vector3.Distance(p,destination))+"}");
        if(!passed) throw new Exception("Pick-and-place did not finish: phase="+phase+", block="+p);
    }
}
public class BlockContacts:MonoBehaviour {
    public Collider left,right;
    readonly HashSet<Collider> touching=new HashSet<Collider>();
    public bool HasLeft=>touching.Contains(left);
    public bool HasRight=>touching.Contains(right);
    void OnCollisionEnter(Collision c) { touching.Add(c.collider); }
    void OnCollisionStay(Collision c) { touching.Add(c.collider); }
    void OnCollisionExit(Collision c) { touching.Remove(c.collider); }
}
