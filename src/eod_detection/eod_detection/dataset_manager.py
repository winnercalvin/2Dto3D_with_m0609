import os
import cv2
import json
import math
import numpy as np
import shutil  
import glob    

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
        self.image_count = 0  # 혹시 몰라 카운터도 0으로 확실히 초기화
        
        # 🔥 [자동 청소기] 스캔 시작 전에 dt 폴더 안의 이전 찌꺼기 싹 지우기!
        self.logger.info("🗑️ 이전 스캔 데이터(찌꺼기)를 자동으로 삭제합니다...")
        try:
            old_files = glob.glob(os.path.join(self.save_dir, '*'))
            for f in old_files:
                if os.path.isfile(f):
                    os.remove(f)
            self.logger.info("✨ 폴더 초기화 완료! 아주 깨끗합니다.")
        except Exception as e:
            self.logger.error(f"❌ 폴더 초기화 실패: {e}")

    def save_image_and_record_pose(self, current_posx):
        # (기존 코드와 완벽히 동일)
        img = self.cam_mgr.get_color_frame()

        if img is not None:
            img_name = f"img_{self.image_count:04d}.jpg"
            filename = os.path.join(self.save_dir, img_name)
            cv2.imwrite(filename, img)

            x, y, z, rx, ry, rz = current_posx
            T_robot = self.cam_mgr.get_robot_pose_matrix(x, y, z, rx, ry, rz)
            T_cam = T_robot @ self.cam_mgr.gripper2cam
            T_cam[:3, 3] = T_cam[:3, 3] / 1000.0

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
        # (기존 코드와 완벽히 동일)
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
        
        # 🌟 JSON 저장이 끝나면 기초 구름 생성 함수를 자동으로 실행합니다!
        self.generate_initial_point_cloud()

    # 🚀 새롭게 추가된 기초 구름(가이드 포인트) 생성기
    def generate_initial_point_cloud(self):
        self.logger.info("☁️ 3DGS 학습을 위한 기초 구름(Point Cloud)을 생성합니다...")
        
        points = []
        colors = []

        # 로봇이 사진을 찍은 모든 좌표를 순회합니다.
        for frame in self.frames_data:
            T_gl = np.array(frame["transform_matrix"])
            
            # 카메라의 현재 위치 (X, Y, Z)
            cam_pos = T_gl[:3, 3]
            
            # OpenGL 좌표계에서 카메라는 Z축의 반대 방향(-Z)을 바라봅니다.
            forward_vec = -T_gl[:3, 2]

            # 💡 카메라 렌즈 앞 20cm ~ 60cm 사이(타코 도마가 있는 예상 위치)에 가상의 점들을 촘촘히 뿌립니다.
            # 작업 환경에 따라 거리를 조절할 수 있습니다 (0.2m ~ 0.6m)
            for depth in np.linspace(0.2, 0.6, 15):
                # 카메라 위치에서 바라보는 방향으로 depth만큼 떨어진 3D 좌표
                point = cam_pos + forward_vec * depth
                
                # 좌우/위아래로 약간의 난수(노이즈)를 줘서 점들을 넓게 퍼트립니다 (반경 5cm)
                noise = np.random.uniform(-0.05, 0.05, 3)
                point_with_noise = point + noise
                
                points.append(point_with_noise)
                # 점의 초기 색상은 튀지 않는 무난한 회색으로 통일합니다.
                colors.append([128, 128, 128])

        # 생성된 점들을 Nerfstudio가 읽을 수 있는 표준 PLY 파일 형식으로 저장합니다. (Open3D 라이브러리 불필요!)
        ply_path = os.path.join(self.save_dir, "points3D.ply")
        with open(ply_path, "w") as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {len(points)}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")
            
            for p, c in zip(points, colors):
                f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {c[0]} {c[1]} {c[2]}\n")

        self.logger.info(f"✅ 기초 구름 생성 완료! 총 {len(points)}개의 가이드 점이 {ply_path}에 저장되었습니다.")