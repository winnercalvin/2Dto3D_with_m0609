import cv2
import rclpy
from rclpy.node import Node

# 분리한 모듈 임포트
from camera_manager import CameraManager
from dataset_manager import DatasetManager

from realsense import ImgNode
from onrobot import RG
import DR_init

# --- 로봇 설정 ---
ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"
VELOCITY, ACC = 10, 10  # 안전한 이동 속도

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL

GRIPPER_NAME = "rg2"
TOOLCHARGER_IP = "192.168.1.1"
TOOLCHARGER_PORT = "502"

TEACHING_WAYPOINTS = [
    [1.49, 41.28, 132.716, 182.946, 81.266, -87.036],       # 1. 기준 시작점 (정확함)
    [-6.888, 43.876, 132.03, 167.908, 84.609, -88.454],     # (중간 궤적 360도 보정 완료)
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
    [-43.133, 73.421, 44.192, 83.962, 93.822, -21.034]      # 21. 기준 도착점 (정확함)
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

class RobotScannerNode(Node):
    def __init__(self):
        super().__init__("robot_scanner_node")
        
        self.img_node = ImgNode()
        self.cam_mgr = CameraManager(self.img_node, self.get_logger())
        self.dataset_mgr = DatasetManager("dt", self.cam_mgr, self.get_logger())
        self.gripper = RG(GRIPPER_NAME, TOOLCHARGER_IP, TOOLCHARGER_PORT)

        self.test_triggered = False

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.test_triggered:
                self.get_logger().info("⏳ 로봇이 이미 스캔 중입니다.")
                return
            self.get_logger().info("🎯 시작! 티칭된 궤적에 따라 스캔을 시작합니다.")
            self.test_triggered = True

    def update_camera_feed(self):
        """이동/대기 중 카메라 화면 멈춤 방지"""
        img = self.cam_mgr.get_color_frame()
        if img is not None:
            cv2.imshow("Webcam", img)
            cv2.waitKey(1)

    def execute_hardcoded_trajectory(self):
        self.get_logger().info("--- 🚀 하드코딩 티칭 궤적 스캔 시작 ---")
        self.dataset_mgr.reset_dataset()

        total_points = len(OPPOSITE_WAYPOINTS)

        for i in range(0, len(TEACHING_WAYPOINTS)):
            self.get_logger().info(f"🤖 [이동 중 {i+1}/{total_points}] Waypoint로 이동합니다...")
            
            target_posj = posj(TEACHING_WAYPOINTS[i])
            
            try:
                # 1. 티칭한 관절 각도 그대로 이동
                movej(target_posj, vel=VELOCITY, acc=ACC)
                self.update_camera_feed()
                
                # 2. 로봇이 완전히 멈추고 카메라가 흔들리지 않도록 잠시 대기
                for _ in range(5):
                    wait(0.1)
                    self.update_camera_feed()

                # 3. 3DGS 학습을 위해 현재 위치의 '진짜 3D 좌표(posx)'를 읽어와서 사진과 함께 저장
                current_posx_val = get_current_posx()[0] 
                self.dataset_mgr.save_image_and_record_pose(current_posx_val)
                self.get_logger().info(f"📸 찰칵! [{i+1}/{total_points}] 저장 완료.")
                
            except Exception as e:
                self.get_logger().error(f"❌ 이동 오류 발생: {e}")
                break
        
        # 첫 번째 시작점 위치로 복귀 (옵션)
        self.get_logger().info("🔄 시작 위치로 복귀합니다.")
        movej(posj([0,0,90,0,90,0]), vel=VELOCITY, acc=ACC)
        self.test_triggered = False
        
        for i, waypoint_j in enumerate(OPPOSITE_WAYPOINTS):
            self.get_logger().info(f"🤖 [이동 중 {i+1}/{total_points}] Waypoint로 이동합니다...")
            
            target_posj = posj(waypoint_j)
            
            try:
                # 1. 티칭한 관절 각도 그대로 이동
                movej(target_posj, vel=VELOCITY, acc=ACC)
                self.update_camera_feed()
                
                # 2. 로봇이 완전히 멈추고 카메라가 흔들리지 않도록 잠시 대기
                for _ in range(5):
                    wait(0.1)
                    self.update_camera_feed()

                # 3. 3DGS 학습을 위해 현재 위치의 '진짜 3D 좌표(posx)'를 읽어와서 사진과 함께 저장
                current_posx_val = get_current_posx()[0] 
                self.dataset_mgr.save_image_and_record_pose(current_posx_val)
                self.get_logger().info(f"📸 찰칵! [{i+1}/{total_points}] 저장 완료.")
                
            except Exception as e:
                self.get_logger().error(f"❌ 이동 오류 발생: {e}")
                break

        # 첫 번째 시작점 위치로 복귀 (옵션)
        self.get_logger().info("🔄 시작 위치로 복귀합니다.")
        movej(posj([0,0,90,0,90,0]), vel=VELOCITY, acc=ACC)
        self.test_triggered = False

        # 전체 궤적 완료 후 데이터 저장
        self.dataset_mgr.save_transforms_json()
        self.get_logger().info("✅ 스캔 완료! 데이터를 성공적으로 저장했습니다.")
        


    def open_img_node(self):
        img = self.cam_mgr.get_color_frame()
        if img is not None:
            cv2.setMouseCallback("Webcam", self.mouse_callback, img)
            cv2.imshow("Webcam", img)

if __name__ == "__main__":
    rclpy.init()
    node = rclpy.create_node("dsr_scanner_node", namespace=ROBOT_ID)
    DR_init.__dsr__node = node

    try:
        from DSR_ROBOT2 import get_current_posx, movej, wait
        from DR_common2 import posj
    except ImportError as e:
        print(f"Error importing DSR_ROBOT2 : {e}")
        exit(True)

    cv2.namedWindow("Webcam")
    scanner_node = RobotScannerNode()

    try:
        while rclpy.ok():
            scanner_node.open_img_node()
            key = cv2.waitKey(1) & 0xFF
            
            if scanner_node.test_triggered:
                scanner_node.execute_hardcoded_trajectory()
                
            if key == 27: # ESC 종료
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if 'scanner_node' in locals():
            scanner_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()