using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Sensor;
using RosMessageTypes.Geometry;
using RosMessageTypes.Trajectory;
using RosMessageTypes.Std;
using RosMessageTypes.BuiltinInterfaces;

public partial class DemoRun : MonoBehaviour
{
    [Serializable] class RendererInfo { public string device,vendor,api; }
    [Serializable] class PolicyConfig { public string[] joint_names; }
    RobotController robot;
    PincherController gripper;
    ArticulationBody[] joints;
    StreamWriter csv, applied, imageTimeline;
    Camera cameraView;
    RenderTexture target;
    Texture2D pixels;
    ROSConnection ros;
    PolicyConfig config;
    string output;
    float duration, started, boot, nextSample, nextFrame, lastCommand;
    double lastStamp=-1;
    double[] velocity = new double[6], driveRadians = new double[6];
    bool finished, ready, pending;
    int frames, commands;
    const double Limit = Math.PI/18;
    const int CaptureFPS=15;
    static string Number(double value) { return value.ToString("R",CultureInfo.InvariantCulture); }
    static PointMsg ToROS(Vector3 p) { return new PointMsg(p.z,-p.x,p.y); }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install() { new GameObject("CookbookRun").AddComponent<DemoRun>(); }

    IEnumerator Start()
    {
        try {
            string raw = Environment.GetEnvironmentVariable("RUN_SECONDS") ?? "180";
            if (!float.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out duration)
                || !float.IsFinite(duration) || duration<5 || duration>600) throw new Exception("RUN_SECONDS must be 5..600");
            output = Environment.GetEnvironmentVariable("OUTPUT_DIR");
            if (String.IsNullOrEmpty(output)) throw new Exception("OUTPUT_DIR is required");
            Directory.CreateDirectory(Path.Combine(output,"images"));
            GameObject.Find("ManualInput")?.SetActive(false);
            robot = FindFirstObjectByType<RobotController>();
            gripper = FindFirstObjectByType<PincherController>();
            cameraView = Camera.main;
            config = JsonUtility.FromJson<PolicyConfig>(File.ReadAllText(Environment.GetEnvironmentVariable("POLICY_CONFIG")));
            if (robot==null || gripper==null || cameraView==null || config.joint_names.Length!=6)
                throw new Exception("Expected six-joint UR3, gripper and camera");
            joints = new ArticulationBody[6];
            foreach (var control in FindObjectsByType<ArticulationJointController>(FindObjectsSortMode.None)) control.enabled=false;
            for(int i=0;i<6;i++) {
                joints[i]=robot.joints[i].robotPart.GetComponent<ArticulationBody>();
                if(joints[i].name!=config.joint_names[i]) throw new Exception("Joint mapping mismatch");
            }
            File.WriteAllText(Path.Combine(output,"renderer.json"),JsonUtility.ToJson(new RendererInfo {
                device=SystemInfo.graphicsDeviceName,vendor=SystemInfo.graphicsDeviceVendor,
                api=SystemInfo.graphicsDeviceType.ToString() }));
            PreparePickScene();
            csv=new StreamWriter(Path.Combine(output,"joints.csv"));
            csv.WriteLine("time_s,joint_0_deg,joint_1_deg,joint_2_deg,joint_3_deg,joint_4_deg,joint_5_deg,grip");
            applied=new StreamWriter(Path.Combine(output,"applied.csv"));
            applied.WriteLine("time_s,observation_stamp,v0,v1,v2,v3,v4,v5");
            imageTimeline=new StreamWriter(Path.Combine(output,"frames.csv"));
            imageTimeline.WriteLine("frame,time_s");
            target=new RenderTexture(640,480,24); target.Create();
            pixels=new Texture2D(640,480,TextureFormat.RGB24,false);
            RenderCamera(); // Warm shaders/readback before the timed control loop.
            Application.targetFrameRate=30; QualitySettings.vSyncCount=0;
            ros=ROSConnection.GetOrCreateInstance(); ros.ConnectOnStart=false;
            ros.RosIPAddress="127.0.0.1"; ros.RosPort=10000;
            ros.RegisterPublisher<JointStateMsg>("/joint_states");
            ros.RegisterPublisher<PointStampedMsg>("/tool_position");
            RegisterPickTopics();
            ros.Subscribe<JointTrajectoryMsg>("/joint_commands", Command);
            ros.Connect(); boot=Time.realtimeSinceStartup;
        } catch(Exception e) { Fail(e); }
        // Scene articulation transforms settle after their first physics updates.
        yield return new WaitForSecondsRealtime(1);
        yield return new WaitForFixedUpdate();
        if (!finished) {
            gripper.grip=0; gripper.gripState=GripState.Fixed;
            for(int i=0;i<6;i++) driveRadians[i]=joints[i].jointPosition[0];
            ready=true; nextSample=Time.realtimeSinceStartup;
        }
    }
    Vector3 Tool() { return robot.transform.InverseTransformPoint(gripper.CurrentGraspCenter()); }
    public static bool FreshCommand(double stamp,double now,double previous) {
        return double.IsFinite(stamp) && stamp>previous && now-stamp>=-.01 && now-stamp<=.5;
    }
    public static void ValidateCommand(JointTrajectoryMsg message,string[] names) {
        if(!message.joint_names.SequenceEqual(names) || message.header.frame_id!="base_link"
            || message.header.stamp.nanosec>=1000000000 || message.points.Length!=1
            || message.points[0].velocities.Length!=6 || message.points[0].positions.Length!=0
            || message.points[0].accelerations.Length!=0 || message.points[0].effort.Length!=0
            || message.points[0].time_from_start.sec!=0 || message.points[0].time_from_start.nanosec!=100000000
            || message.points[0].velocities.Any(v=>!double.IsFinite(v)||Math.Abs(v)>Limit+1e-6))
            throw new Exception("Malformed joint command: expected ordered six rad/s velocities limited to 10 deg/s");
    }
    void Command(JointTrajectoryMsg message) {
        if(finished || !ready) return;
        try {
            double stamp=message.header.stamp.sec+message.header.stamp.nanosec*1e-9;
            ValidateCommand(message,config.joint_names);
            if(!FreshCommand(stamp,Time.realtimeSinceStartup,lastStamp)) return;
            velocity=message.points[0].velocities; lastStamp=stamp; lastCommand=Time.realtimeSinceStartup;
            if(started==0) started=lastCommand;
            commands++;
            pending=true;
        } catch(Exception e) { Fail(e); }
    }
    void FixedUpdate() {
        if(finished || !ready) return;
        bool fresh=started>0 && Time.realtimeSinceStartup-lastCommand<.5f;
        for(int i=0;i<6;i++) {
            var drive=joints[i].xDrive;
            // Hold a persistent target; resetting it to measured position accumulates gravity drift.
            if(fresh) driveRadians[i]+=velocity[i]*Time.fixedDeltaTime;
            drive.target=(float)driveRadians[i]*Mathf.Rad2Deg;
            joints[i].xDrive=drive;
        }
        if(pending && fresh) {
            applied.WriteLine(Number(Time.realtimeSinceStartup-started)+","+Number(lastStamp)+","+String.Join(",",velocity.Select(Number))); applied.Flush();
            pending=false;
        }
    }
    void Update() {
        if(finished || !ready) return;
        try {
            float now=Time.realtimeSinceStartup;
            if(started==0 && now-boot>30) throw new Exception("ROS policy handshake timed out");
            if(started>0 && now-lastCommand>2) throw new Exception("ROS commands stale for two seconds");
            float elapsed=started>0?now-started:0;
            if(now>=nextSample) {
                var header=new HeaderMsg(new TimeMsg((int)now,(uint)((now-(int)now)*1e9)),"base_link");
                ros.Publish("/joint_states",new JointStateMsg(header,config.joint_names,joints.Select(j=>(double)j.jointPosition[0]).ToArray(),joints.Select(j=>(double)j.jointVelocity[0]).ToArray(),new double[0]));
                ros.Publish("/tool_position",new PointStampedMsg(header,ToROS(Tool())));
                PublishPick(header,elapsed);
                if(started>0) {
                    csv.WriteLine(Number(elapsed)+","+String.Join(",",joints.Select(j=>Number(j.jointPosition[0]*Mathf.Rad2Deg)))+","+Number(gripper.CurrentGrip())); csv.Flush();
                }
                nextSample=Math.Max(nextSample+.1f,now);
            }
            PublishVision(new HeaderMsg(new TimeMsg((int)now,(uint)((now-(int)now)*1e9)),"base_link"),now);
            if(started>0 && elapsed>=nextFrame) {
                RenderCamera();
                File.WriteAllBytes(Path.Combine(output,"images","frame_"+frames.ToString("D5")+".png"),pixels.EncodeToPNG());
                imageTimeline.WriteLine(frames+","+Number(elapsed));
                frames++; nextFrame=Math.Max(nextFrame+1f/CaptureFPS,elapsed);
            }
            if(started>0 && (elapsed>=duration || completedAt>=0 && elapsed-completedAt>=3)) {
                FinishPick(); finished=true; Close();
                File.WriteAllText(Path.Combine(output,"simulation.json"),"{\"duration_seconds\":"+Number(elapsed)+",\"capture_fps\":"+CaptureFPS+",\"frames\":"+frames+",\"commands\":"+commands+"}");
                Application.Quit(0);
            }
        } catch(Exception e) { Fail(e); }
    }
    void RenderCamera() {
        cameraView.targetTexture=target; cameraView.Render(); RenderTexture.active=target;
        pixels.ReadPixels(new Rect(0,0,640,480),0,0); pixels.Apply();
        RenderTexture.active=null; cameraView.targetTexture=null;
    }
    void Close() { imageTimeline?.Dispose(); imageTimeline=null; csv?.Dispose(); applied?.Dispose(); objects?.Dispose(); objects=null; csv=applied=null; }
    void Fail(Exception e) { finished=true; Close(); Debug.LogException(e); Application.Quit(1); }
    void OnDestroy() { Close(); }
}
