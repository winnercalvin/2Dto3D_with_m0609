import rclpy
import time
import numpy as np
from scipy.spatial.transform import Rotation

class CameraManager:
    def __init__(self, img_node, logger):
        self.img_node = img_node
        self.logger = logger
        self.intrinsics = None
        
        # Hand-Eye 보정 매트릭스 로드
        self.gripper2cam = np.load("/home/rokey/EOD_ws/src/eod_detection/weights/T_gripper2camera_long.npy")

        self.logger.info("⏳ 카메라 파라미터(intrinsics) 수신 대기 중...")
        while self.intrinsics is None:
            rclpy.spin_once(self.img_node, timeout_sec=0.5)
            self.intrinsics = self.img_node.get_camera_intrinsic()
            time.sleep(0.5)
        self.logger.info("✅ 카메라 파라미터 수신 완료!")

    def get_color_frame(self):
        rclpy.spin_once(self.img_node)
        return self.img_node.get_color_frame()

    def get_depth_frame(self):
        rclpy.spin_once(self.img_node)
        return self.img_node.get_depth_frame()

    def get_depth_value(self, center_x, center_y, depth_frame):
        height, width = depth_frame.shape
        if 0 <= center_x < width and 0 <= center_y < height:
            return depth_frame[center_y, center_x]
        self.logger.warn(f"out of image range: {center_x}, {center_y}")
        return None

    def get_camera_pos(self, center_x, center_y, center_z):
        camera_x = (center_x - self.intrinsics["ppx"]) * center_z / self.intrinsics["fx"]
        camera_y = (center_y - self.intrinsics["ppy"]) * center_z / self.intrinsics["fy"]
        camera_z = center_z
        return (camera_x, camera_y, camera_z)

    def get_robot_pose_matrix(self, x, y, z, rx, ry, rz):
        R = Rotation.from_euler("ZYZ", [rx, ry, rz], degrees=True).as_matrix()
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [x, y, z]
        return T

    def transform_to_base(self, camera_coords, current_robot_posx):
        coord = np.append(np.array(camera_coords), 1)
        base2gripper = self.get_robot_pose_matrix(*current_robot_posx)
        base2cam = base2gripper @ self.gripper2cam
        td_coord = np.dot(base2cam, coord)
        return td_coord[:3]