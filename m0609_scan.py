import cv2
import rclpy
from rclpy.node import Node
import math
import numpy as np

# 분리한 모듈 임포트
from camera_manager import CameraManager
from dataset_manager import DatasetManager

from realsense import ImgNode
from scipy.spatial.transform import Rotation
from onrobot import RG
import DR_init

# --- 로봇 설정 ---
ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"
VELOCITY, ACC = 60, 60

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL

GRIPPER_NAME = "rg2"
TOOLCHARGER_IP = "192.168.1.1"
TOOLCHARGER_PORT = "502"

# --- 스캔 설정 ---
SCAN_RADIUS = 100.0   
SCAN_Z_OFFSET = 150.0 
NUM_IMAGES = 36       

class RobotScannerNode(Node):
    def __init__(self):
        super().__init__("robot_scanner_node")
        
        self.img_node = ImgNode()
        
        # 외부 클래스 인스턴스화
        self.cam_mgr = CameraManager(self.img_node, self.get_logger())
        self.dataset_mgr = DatasetManager("dt", self.cam_mgr, self.get_logger())

        self.gripper = RG(GRIPPER_NAME, TOOLCHARGER_IP, TOOLCHARGER_PORT)
        
        self.JReady = posj([0, 0, 90, 0, 90, -90])
        self.current_sol_space = 0 

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            depth_frame = self.cam_mgr.get_depth_frame()
            while depth_frame is None or np.all(depth_frame == 0):
                self.get_logger().info("retry get depth img")
                depth_frame = self.cam_mgr.get_depth_frame()

            z = self.cam_mgr.get_depth_value(x, y, depth_frame)
            camera_center_pos = self.cam_mgr.get_camera_pos(x, y, z)
            
            current_posx = get_current_posx()[0]
            robot_coordinate = self.cam_mgr.transform_to_base(camera_center_pos, current_posx)
            print(f"🎯 Target robot cordinate: ({robot_coordinate})")

            self.scan_360_around_target(*robot_coordinate)

    def calculate_lookat_zyz(self, cam_x, cam_y, cam_z, tx, ty, tz):
        cam_pos = np.array([cam_x, cam_y, cam_z])
        target_pos = np.array([tx, ty, tz])

        forward = target_pos - cam_pos
        forward = forward / np.linalg.norm(forward)

        world_up = np.array([0, 0, 1])
        if abs(np.dot(forward, world_up)) > 0.99:
            world_up = np.array([1, 0, 0])

        right = np.cross(world_up, forward)
        right = right / np.linalg.norm(right)

        down = np.cross(forward, right)

        R_mat = np.column_stack((right, down, forward))
        r = Rotation.from_matrix(R_mat)
        zyz = r.as_euler('ZYZ', degrees=True)
        return zyz[0], zyz[1], zyz[2]

    def scan_360_around_target(self, tx, ty, tz):
        self.get_logger().info(f"📸 좌표({tx:.1f}, {ty:.1f}, {tz:.1f}) 중심으로 스캔을 시작합니다.")
        self.dataset_mgr.reset_dataset()

        # 현재 자세 번호 고정
        self.current_sol_space = get_current_solution_space()
        
        half_steps = NUM_IMAGES // 2

        self.get_logger().info("--- 1차 스캔 시작 ---")
        for step in range(half_steps):
            self._move_and_capture(step, tx, ty, tz)

        self.get_logger().info("🔄 관절을 풀기 위해 홈 위치 복귀")
        movej(self.JReady, vel=VELOCITY, acc=ACC)
        wait(1.5)

        self.get_logger().info("--- 2차 스캔 시작 ---")
        for step in range(half_steps, NUM_IMAGES):
            self._move_and_capture(step, tx, ty, tz)

        self.dataset_mgr.save_transforms_json()
        self.get_logger().info("✅ 스캔 완료!")
        movej(self.JReady, vel=VELOCITY, acc=ACC)

    def _move_and_capture(self, step, tx, ty, tz):
        theta_rad = math.radians(step * (360.0 / NUM_IMAGES))

        cam_x = tx + SCAN_RADIUS * math.cos(theta_rad)
        cam_y = ty + SCAN_RADIUS * math.sin(theta_rad)
        cam_z = tz + SCAN_Z_OFFSET

        rx, ry, rz = self.calculate_lookat_zyz(cam_x, cam_y, cam_z, tx, ty, tz)
        target_posx = posx([cam_x, cam_y, cam_z, rx, ry, rz])
        target_posj = ikin(target_posx, self.current_sol_space, 0, 0, [0.005, 0.0])
        
        if target_posj is None:
            self.get_logger().warn(f"⚠️ [{step+1}/{NUM_IMAGES}] 특이점 발생.")
            return

        movej(target_posj, vel=VELOCITY, acc=ACC)
        wait(0.5)
        
        self.dataset_mgr.save_image_and_record_pose(target_posx)

    def open_img_node(self):
        img = self.cam_mgr.get_color_frame()
        if img is not None:
            cv2.setMouseCallback("Webcam", self.mouse_callback, img)
            cv2.imshow("Webcam", img)

if __name__ == "__main__":
    rclpy.init()
    node = rclpy.create_node("dsr_scanner_node", namespace=ROBOT_ID)
    DR_init.__dsr__node = node

    # ROS 노드 초기화 이후에 로봇 명령어 임포트 수행 (Doosan API 규칙)
    try:
        from DSR_ROBOT2 import get_current_posx, movej, movel, wait, ikin, get_current_solution_space
        from DR_common2 import posx, posj
    except ImportError as e:
        print(f"Error importing DSR_ROBOT2 : {e}")
        exit(True)

    cv2.namedWindow("Webcam")
    scanner_node = RobotScannerNode()

    try:
        while True:
            scanner_node.open_img_node()
            if cv2.waitKey(1) & 0xFF == 27:  # ESC 키로 종료
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        scanner_node.destroy_node()
        rclpy.shutdown()