import os
import cv2
import json
import math
import numpy as np

class DatasetManager:
    def __init__(self, save_dir, camera_manager, logger):
        self.save_dir = save_dir
        self.cam_mgr = camera_manager
        self.logger = logger
        
        os.makedirs(self.save_dir, exist_ok=True)
        self.image_count = 0
        self.frames_data = []

    def reset_dataset(self):
        self.frames_data = []

    def save_image_and_record_pose(self, current_posx):
        img = self.cam_mgr.get_color_frame()

        if img is not None:
            img_name = f"img_{self.image_count:04d}.jpg"
            filename = os.path.join(self.save_dir, img_name)
            cv2.imwrite(filename, img)

            # 1. 로봇 TCP 좌표 행렬
            x, y, z, rx, ry, rz = current_posx
            T_robot = self.cam_mgr.get_robot_pose_matrix(x, y, z, rx, ry, rz)

            # 2. Hand-Eye 보정 (로봇 TCP -> 실제 렌즈 중심)
            T_cam = T_robot @ self.cam_mgr.gripper2cam

            # 3. 가우시안 스플래팅 필수: Translation 단위를 mm -> m 로 변환
            T_cam[:3, 3] = T_cam[:3, 3] / 1000.0

            # 4. 가우시안 스플래팅 필수: OpenCV -> OpenGL 좌표계 변환
            cv2gl_matrix = np.array([
                [1,  0,  0, 0],
                [0, -1,  0, 0],
                [0,  0, -1, 0],
                [0,  0,  0, 1]
            ])
            T_gl = T_cam @ cv2gl_matrix

            self.frames_data.append({
                "file_path": img_name,
                "transform_matrix": T_gl.tolist()
            })

            self.logger.info(f"포즈 기록 완료: {img_name}")
            self.image_count += 1
        else:
            self.logger.warn("⚠️ 프레임 누락됨")

    def save_transforms_json(self):
        intrinsics = self.cam_mgr.intrinsics
        fl_x = intrinsics.get("fx", 0)
        fl_y = intrinsics.get("fy", 0)
        cx = intrinsics.get("ppx", 0)
        cy = intrinsics.get("ppy", 0)

        img = self.cam_mgr.get_color_frame()
        h, w = img.shape[:2] if img is not None else (720, 1280)

        camera_angle_x = 2.0 * math.atan(w / (2.0 * fl_x)) if fl_x > 0 else 0

        out_dict = {
            "camera_angle_x": camera_angle_x,
            "fl_x": fl_x, "fl_y": fl_y,
            "cx": cx, "cy": cy,
            "w": w, "h": h,
            "frames": self.frames_data
        }

        json_path = os.path.join(self.save_dir, "transforms_train.json")
        with open(json_path, "w") as f:
            json.dump(out_dict, f, indent=4)
        self.logger.info(f"🎉 데이터셋 완성: {json_path}")