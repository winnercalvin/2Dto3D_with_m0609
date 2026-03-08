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
        self.gripper2cam = np.load("T_gripper2camera.npy")

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
    
    def get_3dgs_transform_matrix(self, current_robot_posx):
        """
        현재 로봇 좌표를 받아서 3DGS JSON에 들어갈 완벽한 OpenGL 기준 C2W 행렬을 반환합니다.
        """
        x, y, z, rx, ry, rz = current_robot_posx
        
        # 🚨 중요 1: 단위 변환 (밀리미터 -> 미터)
        # 만약 이미 미터(m) 단위로 받고 계시다면 이 부분을 지워주세요!
        x_m = x / 1000.0
        y_m = y / 1000.0
        z_m = z / 1000.0
        
        # 1. 그리퍼의 월드 좌표 구하기 (미터 단위 적용)
        base2gripper = self.get_robot_pose_matrix(x_m, y_m, z_m, rx, ry, rz)
        
        # 🚨 핸드아이 매트릭스 단위 체크!
        # self.gripper2cam 안의 평행이동(Translation) 값도 반드시 '미터(m)' 단위여야 합니다.
        base2cam = base2gripper @ self.gripper2cam  # OpenCV 기준 완벽한 C2W 행렬
        
        # 🚨 중요 2: 3DGS용 OpenGL 좌표계 변환 (Y, Z축 뒤집기)
        c2w_opengl = base2cam.copy()
        c2w_opengl[:, 1] *= -1  # Y축 반전
        c2w_opengl[:, 2] *= -1  # Z축 반전
        
        return c2w_opengl.tolist()  # JSON에 바로 넣을 수 있게 리스트로 반환