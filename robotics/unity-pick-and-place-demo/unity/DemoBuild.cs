using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class DemoBuild
{
    [Serializable] public class Joint {
        public string name;
        public Vector3 parentPosition, childPosition;
        public Quaternion parentRotation, childRotation;
    }
    [Serializable] public class Chain {
        public Joint[] joints;
        public Vector3 tip, initialTool;
        public Quaternion tipRotation;
    }
    public static void ExportKinematics() {
        EditorSceneManager.OpenScene("Assets/Scenes/ArticulationRobot.unity");
        var robot = UnityEngine.Object.FindFirstObjectByType<RobotController>();
        var grip = UnityEngine.Object.FindFirstObjectByType<PincherController>();
        var chain = new Chain { joints = new Joint[6] };
        for (int i = 0; i < 6; i++) {
            var body = robot.joints[i].robotPart.GetComponent<ArticulationBody>();
            chain.joints[i] = new Joint { name = body.name, parentPosition = body.parentAnchorPosition,
                childPosition = body.anchorPosition, parentRotation = body.parentAnchorRotation,
                childRotation = body.anchorRotation };
        }
        var centre=grip.transform.TransformPoint((grip.fingerA.transform.localPosition+grip.fingerB.transform.localPosition)/2);
        var last=robot.joints[5].robotPart.transform;
        chain.tip = last.InverseTransformPoint(centre);
        chain.tipRotation=Quaternion.Inverse(last.rotation)*grip.transform.rotation;
        chain.initialTool = robot.transform.InverseTransformPoint(centre);
        File.WriteAllText(Environment.GetEnvironmentVariable("KINEMATICS_PATH"), JsonUtility.ToJson(chain, true));
    }
    public static void ValidateContract() {
        string[] names={"Base","Shoulder","Elbow","Wrist1","Wrist2","Wrist3"};
        var point=new RosMessageTypes.Trajectory.JointTrajectoryPointMsg();
        point.velocities=new double[6]; point.time_from_start.nanosec=100000000;
        var command=new RosMessageTypes.Trajectory.JointTrajectoryMsg();
        command.header.frame_id="base_link"; command.joint_names=names;
        command.points=new[] {point};
        DemoRun.ValidateCommand(command,names);
        foreach(double invalid in new[] {10.0,double.NaN,double.PositiveInfinity}) {
            point.velocities[0]=invalid;
            bool rejected=false;
            try { DemoRun.ValidateCommand(command,names); } catch(Exception) { rejected=true; }
            if(!rejected) throw new Exception("Velocity units/finite check failed");
        }
        point.velocities[0]=Math.PI/18;
        DemoRun.ValidateCommand(command,names);
        command.joint_names=new[] {"Shoulder","Base","Elbow","Wrist1","Wrist2","Wrist3"};
        bool wrongOrder=false;
        try { DemoRun.ValidateCommand(command,names); } catch(Exception) { wrongOrder=true; }
        if(!wrongOrder || DemoRun.FreshCommand(1,1.6,0) || DemoRun.FreshCommand(1,1,1)
            || DemoRun.FreshCommand(2,1,0) || !DemoRun.FreshCommand(1,1.1,0))
            throw new Exception("Joint order or stale command check failed");
        Debug.Log("ROS command joint mapping, radians, limits and stale timestamp checks passed");
    }
    public static void Linux()
    {
        if (Application.unityVersion != "6000.6.5f1") throw new Exception("Use Unity 6000.6.5f1");
        if (!PlayerSettings.GetScriptingDefineSymbolsForGroup(BuildTargetGroup.Standalone).Contains("ROS2"))
            throw new Exception("Enable ROS2 under Player Settings > Scripting Define Symbols before building");
        string output = Environment.GetEnvironmentVariable("UNITY_BUILD_DIR");
        if (String.IsNullOrEmpty(output) || !Path.IsPathRooted(output) || Directory.Exists(output))
            throw new Exception("UNITY_BUILD_DIR must be absolute and fresh");
        ValidateContract();
        Directory.CreateDirectory(output);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { "Assets/Scenes/ArticulationRobot.unity" },
            locationPathName = Path.Combine(output, "UnityRobot.x86_64"),
            target = BuildTarget.StandaloneLinux64, options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded) throw new Exception("Linux player build failed");
        File.WriteAllText(Path.Combine(output, "build.json"),
            "{\"editor_version\":\"" + Application.unityVersion + "\",\"source_revision\":\"111705a8a4417fb7fe1816f46daa67ef01342464\",\"ros\":2}");
    }
}
