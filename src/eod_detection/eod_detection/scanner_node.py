import cv2
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool 
import time
import math

# 🔥 [수정됨] 패키지 내부 모듈 임포트 (eod_detection 명시!)
from eod_detection.camera_manager import CameraManager
from eod_detection.dataset_manager import DatasetManager
from eod_detection.realsense import ImgNode
from eod_detection.onrobot import RG

# ROS2 네이티브 모션 제어
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint

# 실시간 로봇 좌표 획득을 위한 TF 라이브러리
from tf2_ros import Buffer, TransformListener
from scipy.spatial.transform import Rotation as SciPyRotation

# --- 로봇 설정 ---
GRIPPER_NAME = "rg2"
TOOLCHARGER_IP = "192.168.1.1"
TOOLCHARGER_PORT = "502"

# --- 웨이포인트(경로) 설정 ---
TEACHING_WAYPOINTS = [
    [1.49, 41.28, 132.716, 182.946, 81.266, -87.036],
    [-6.888, 43.876, 132.03, 167.908, 84.609, -88.454],
    [-13.108, 44.271, 132.431, 161.163, 85.115, -88.454],
    [-16.842, 44.285, 130.883, 153.692, 83.695, -88.454],
    [-20.686, 44.555, 128.622, 147.008, 81.42, -88.325],
    [-24.511, 45.039, 125.33, 140.679, 79.683, -84.302],
    [-28.487, 45.678, 121.535, 134.324, 77.655, -81.429],
    [-31.787, 46.382, 117.038, 125.674, 76.207, -75.111],
    [-34.054, 47.702, 112.787, 119.63, 76.461, -71.56],
    [-36.819, 49.558, 107.118, 112.818, 76.968, -67.864],
    [-37.743, 50.876, 103.007, 109.688, 76.954, -64.33],
    [-39.112, 53.075, 97.776, 104.246, 79.167, -59.37],
    [-40.171, 55.964, 89.551, 98.565, 80.431, -56.934],
    [-40.783, 58.773, 82.264, 94.175, 81.649, -53.22],
    [-40.783, 62.051, 73.952, 90.451, 83.852, -43.515],
    [-40.738, 64.781, 67.517, 88.056, 86.096, -40.241],
    [-40.855, 67.844, 61.564, 87.007, 88.269, -40.114],
    [-41.054, 71.449, 53.927, 85.526, 91.019, -36.159],
    [-41.003, 74.279, 48.352, 83.538, 95.075, -34.839],
    [-40.838, 79.284, 38.872, 84.509, 98.579, -29.398],
    [-43.133, 73.421, 44.192, 83.962, 93.822, -21.034]
]

OPPOSITE_WAYPOINTS = [
    [3.012, 41.614, 131.026, 5.355, -79.82, 90.776],
    [10.919, 41.775, 130.879, 20.964, -79.59, 88.243],
    [17.595, 41.874, 129.237, 31.065, -79.723, 86.082],
    [20.607, 42.209, 128.219, 36.336, -78.85, 86.015],
    [26.477, 42.384, 125.411, 45.587, -78.309, 82.835],
    [29.407, 42.466, 124.336, 51.37, -77.703, 80.817],
    [32.483, 43.557, 120.798, 56.233, -77.759, 79.035],
    [36.423, 43.894, 118.535, 62.28, -78.289, 78.415],
    [38.993, 45.655, 114.058, 68.204, -79.917, 78.389],
    [42.508, 47.152, 109.943, 72.814, -78.986, 75.861],
    [44.704, 48.411, 105.045, 78.448, -79.807, 70.429],
    [47.177, 51.175, 96.651, 85.565, -83.097, 64.137],
    [48.832, 54.819, 86.36, 90.455, -84.462, 57.043],
    [49.362, 57.853, 78.145, 93.199, -85.47, 54.898],
    [49.432, 60.614, 70.006, 95.679, -87.358, 49.525],
    [49.244, 63.765, 61.495, 97.515, -88.898, 42.992],
    [48.964, 66.284, 55.17, 99.315, -91.238, 40.592],
    [48.642, 69.875, 45.962, 100.605, -93.557, 34.538],
    [48.144, 73.283, 38.483, 101.116, -96.159, 24.934]
]

RIGHT_45 = [
    [41.29, 66.947, 37.812, 108.392, -95.449, 10.645],
    [41.286, 54.104, 60.135, 109.84, -85.504, 14.067],
    [40.981, 47.014, 70.889, 109.167, -79.673, 17.159],
    [40.798, 41.697, 78.302, 109.068, -76.724, 17.158],
    [40.373, 35.133, 87.9, 106.189, -71.939, 17.158],
    [38.231, 27.386, 98.917, 104.199, -63.787, 18.382],
    [34.448, 19.591, 108.22, 98.436, -52.802, 18.381],
    [30.73, 13.931, 114.362, 93.653, -45.39, 18.38],
    [21.398, 5.961, 121.589, 86.199, -30.132, 18.382],
    [11.981, 1.954, 125.113, 77.462, -18.508, 20.467],
    [5.234, 5.722, 119.97, 60.892, -9.006, 33.042],
    [7.068, 12.58, 118.089, 45.668, -17.278, 48.536],
    [-0.508, 12.784, 110.413, 88.013, -1.779, 2.284],
    [-7.269, 13.693, 109.5, 86.173, 11.13, 2.219],
    [-10.507, 14.27, 108.793, 84.386, 15.602, 2.2],
    [-15.473, 15.444, 107.481, 81.497, 22.839, 1.071],
    [-19.002, 16.877, 105.593, 77.55, 28.999, -1.567],
    [-21.42, 19.442, 102.707, 76.156, 33.616, -6.737],
    [-23.925, 22.205, 97.188, 70.602, 38.186, -4.99],
    [-26.181, 25.313, 93.773, 69.336, 42.151, -6.282],
    [-32.235, 27.378, 89.776, 67.702, 53.11, -9.531],
    [-33.904, 30.894, 85.851, 67.924, 57.993, -14.996],
    [-35.537, 39.15, 74.566, 64.959, 66.55, -15.839],
    [-37.431, 46.748, 63.715, 65.552, 71.161, -15.616],
    [-38.438, 51.341, 54.298, 62.856, 76.354, -14.588],
    [-39.168, 58.204, 42.591, 62.717, 84.897, -10.353],
    [-38.715, 62.288, 35.774, 62.61, 87.46, -9.457],
    [-38.396, 66.144, 29.639, 63.361, 89.857, -8.1],
    [-38.883, 68.878, 25.792, 64.682, 91.035, -4.963]
]

LEFT_85 = [
    [-31.603, 57.679, 24.253, 46.075, 89.594, 8.696],
    [-29.611, 44.985, 45.792, 43.932, 77.426, 10.157],
    [-28.575, 39.881, 54.609, 42.982, 72.286, 10.157],
    [-26.806, 33.065, 65.529, 42.941, 65.104, 10.157],
    [-25.064, 28.06, 73.271, 42.95, 59.147, 12.03],
    [-22.301, 22.425, 80.101, 40.782, 52.378, 24.656],
    [-18.412, 17.075, 88.295, 39.048, 43.162, 37.909],
    [-12.162, 12.496, 97.298, 33.203, 28.445, 43.914],
    [-7.36, 12.104, 97.791, 20.388, 26.385, 62.047],
    [0.065, 12.169, 93.268, -0.887, 30.09, 90.293],
    [9.475, 13.655, 94.297, -27.586, 28.806, 120.256],
    [11.356, 12.333, 93.293, -31.776, 35.497, 124.234],
    [23.562, 15.669, 95.9, -56.067, 44.676, 165.715],
    [28.492, 19.449, 90.595, -58.565, 50.062, 174.427],
    [33.255, 24.882, 84.197, -60.863, 60.431, 184.655],
    [35.321, 29.049, 79.856, -59.935, 65.125, 187.639],
    [37.742, 32.868, 69.699, -54.468, 73.742, 178.158],
    [37.421, 37.591, 61.907, -54.671, 79.061, 178.082],
    [36.512, 45.345, 49.602, -52.848, 87.027, 178.086],
    [35.975, 48.656, 45.431, -53.003, 89.032, 177.679],
    [35.392, 52.261, 39.26, -53.867, 93.235, 177.0],
    [35.627, 55.628, 32.393, -55.041, 97.465, 170.072],
    [33.428, 62.275, 16.389, -53.287, 101.037, 158.285]
]

class RobotScannerNode(Node):
    def __init__(self):
        super().__init__("robot_scanner_node")
        
        self.img_node = ImgNode()
        self.cam_mgr = CameraManager(self.img_node, self.get_logger())
        
        save_path = "/home/rokey/robot_share/dt"
        self.dataset_mgr = DatasetManager(save_path, self.cam_mgr, self.get_logger())
        
        self.test_triggered = False

        self.trigger_sub = self.create_subscription(Bool, '/trigger_eod_scan', self.trigger_callback, 10)
        self.traj_client = ActionClient(self, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
        
        # TF 버퍼 및 리스너 생성 (실제 위치 추적용)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        self.get_logger().info("📡 AI 통제 노드의 스캔 명령을 기다리고 있습니다...")

    def trigger_callback(self, msg):
        if msg.data and not self.test_triggered:
            self.get_logger().warn("🚨 AI 판독 결과 '위험' 수신! 자동으로 3DGS 스캔 궤적을 시작합니다!")
            self.test_triggered = True

    def update_camera_feed(self):
        img = self.cam_mgr.get_color_frame()
        if img is not None:
            cv2.imshow("Webcam", img)
            cv2.waitKey(1)

    def send_joint_goal_sync(self, j_deg, duration=2.0):
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6']
        
        point = JointTrajectoryPoint()
        point.positions = [math.radians(x) for x in j_deg]
        point.time_from_start.sec = int(duration)
        point.time_from_start.nanosec = int((duration % 1) * 1e9)
        goal_msg.trajectory.points.append(point)
        
        self.traj_client.wait_for_server()
        send_goal_future = self.traj_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error('이동 명령 거부됨')
            return False
            
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        return True

    def get_current_tcp_pose(self):
        try:
            now = rclpy.time.Time()
            trans = self.tf_buffer.lookup_transform('world', 'rg2_tcp', now, rclpy.duration.Duration(seconds=1.0))
            
            tx = trans.transform.translation.x * 1000.0
            ty = trans.transform.translation.y * 1000.0
            tz = trans.transform.translation.z * 1000.0
            
            qx = trans.transform.rotation.x
            qy = trans.transform.rotation.y
            qz = trans.transform.rotation.z
            qw = trans.transform.rotation.w
            r = SciPyRotation.from_quat([qx, qy, qz, qw])
            rx, ry, rz = r.as_euler('ZYZ', degrees=True)
            
            return [tx, ty, tz, rx, ry, rz]
            
        except Exception as e:
            self.get_logger().error(f"❌ 실시간 좌표 획득 실패: {e}")
            return None

    def execute_hardcoded_trajectory(self):
        self.get_logger().info("--- 🚀 3DGS 스캔 시작 ---")
        self.dataset_mgr.reset_dataset()

        def process_waypoints(waypoints_list, reverse=False, initial_duration=6.0, normal_duration=1.5):
            pts = list(reversed(waypoints_list)) if reverse else waypoints_list
            
            for i, target_j in enumerate(pts):
                current_duration = initial_duration if i == 0 else normal_duration
                
                self.get_logger().info(f"🤖 [이동 중] Waypoint로 이동... (소요 시간: {current_duration}초)")
                try:
                    self.send_joint_goal_sync(target_j, duration=current_duration)
                    
                    for _ in range(5):
                        time.sleep(0.1)
                        self.update_camera_feed()

                    current_posx_val = self.get_current_tcp_pose()
                    if current_posx_val is not None:
                        self.dataset_mgr.save_image_and_record_pose(current_posx_val)
                        self.get_logger().info(f"📸 찰칵! 저장 완료. (X: {current_posx_val[0]:.1f}, Y: {current_posx_val[1]:.1f}, Z: {current_posx_val[2]:.1f})")
                    
                except Exception as e:
                    self.get_logger().error(f"❌ 이동 오류: {e}")
                    break

        process_waypoints(TEACHING_WAYPOINTS, reverse=True, initial_duration=8.0, normal_duration=1.5)
        self.send_joint_goal_sync([0,0,90,0,90,0], duration=8.0)
        self.send_joint_goal_sync([0, 0, 0, 5.355, -79.82, 90.776], duration=10.0)
        
        process_waypoints(OPPOSITE_WAYPOINTS, initial_duration=6.0, normal_duration=1.5)
        process_waypoints(RIGHT_45, initial_duration=6.0, normal_duration=1.5)
        process_waypoints(LEFT_85, initial_duration=6.0, normal_duration=1.5)

        self.get_logger().info("🔄 스캔 종료 최종 복귀...")
        self.send_joint_goal_sync([0,0,90,0,90,0], duration=8.0)
        self.test_triggered = False

        self.dataset_mgr.save_transforms_json()
        self.get_logger().info("✅ 스캔 완료! 데이터를 성공적으로 저장했습니다.")

    def open_img_node(self):
        img = self.cam_mgr.get_color_frame()
        if img is not None:
            cv2.imshow("Webcam", img)
            cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    cv2.namedWindow("Webcam")
    scanner_node = RobotScannerNode()

    try:
        while rclpy.ok():
            scanner_node.open_img_node()
            key = cv2.waitKey(1) & 0xFF
            
            rclpy.spin_once(scanner_node, timeout_sec=0.01)
            
            if scanner_node.test_triggered:
                scanner_node.execute_hardcoded_trajectory()
                
            if key == 27: 
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        scanner_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()