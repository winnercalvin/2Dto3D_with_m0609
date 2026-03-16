import os
import json
import open3d as o3d
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

class PointCloudProcessor:
    def __init__(self, ply_path, output_json_path, output_obj_path, voxel_size=0.05, alpha_size=0.02,
                 approach_standoff_m=0.03, z_offset_mm=0.0,
                 max_xy_reach_mm=800.0, min_tcp_z_mm=30.0):
        self.ply_path = ply_path
        self.output_json_path = output_json_path
        self.output_obj_path = output_obj_path
        self.voxel_size = voxel_size
        self.alpha_size = alpha_size
        # 공구중심점(TCP) 오프셋 z=230mm이 로봇 컨트롤러에 이미 설정되어 있으므로
        # 그리퍼 길이는 여기서 더하지 않음. 표면에서 살짝 띄운 접근 여유거리만 설정 (기본 30mm)
        self.approach_standoff_m = approach_standoff_m
        self.z_offset_mm = z_offset_mm        # 미세 보정용 (기본 0)
        # m0609 실질 도달 한계: 3D 거리가 아닌 수평(XY) 거리 기준
        self.max_xy_reach_mm = max_xy_reach_mm  # 수평 도달거리 (기본 800mm)
        self.min_tcp_z_mm = min_tcp_z_mm        # 최소 높이 — 바닥 충돌 방지 (기본 30mm)
        self.mesh = None
        self.voxel_points = None

    @staticmethod
    def _normal_to_rotation_matrix(normal):
        """
        법선벡터(그리퍼 접근방향 = -normal)로부터 완전한 3x3 회전행렬을 계산.
        그리퍼 Z축이 물체 표면을 향하도록(-normal 방향) 정의.
        """
        z_axis = -np.array(normal, dtype=float)  # 그리퍼는 법선 반대로 들어감
        norm = np.linalg.norm(z_axis)
        if norm < 1e-6:
            return np.eye(3)
        z_axis /= norm

        # Gimbal lock 방지: z축과 가장 수직인 참조벡터 선택
        ref = np.array([1.0, 0.0, 0.0]) if abs(z_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])

        y_axis = np.cross(z_axis, ref)
        y_axis /= np.linalg.norm(y_axis)
        x_axis = np.cross(y_axis, z_axis)

        return np.column_stack([x_axis, y_axis, z_axis])

    @staticmethod
    def _rotation_matrix_to_zyz_deg(R_mat):
        """회전행렬 → Doosan DSR ZYZ Euler (degrees). 반드시 degrees=True."""
        rot = Rotation.from_matrix(R_mat)
        rx, ry, rz = rot.as_euler('ZYZ', degrees=True)  # ← degrees=True 필수!
        return float(rx), float(ry), float(rz)

    def load_and_meshify(self):
        if not os.path.exists(self.ply_path):
            print(f"❌ '{self.ply_path}' 파일을 찾을 수 없습니다.")
            return

        print(f"📥 1. 포인트 클라우드 로드 중: '{self.ply_path}'")
        pcd = o3d.io.read_point_cloud(self.ply_path)

        # 1단계: 주변 노이즈(먼지) 제거
        print("🧹 2. 주변 노이즈(Outlier) 통계적 제거 중...")
        pcd_clean, ind = pcd.remove_statistical_outlier(nb_neighbors=40, std_ratio=1.0)
        
        # 노이즈가 제거된 깔끔한 포인트 클라우드만 선택
        pcd_clean = pcd.select_by_index(ind)

        print(f"🕸️ 3. Alpha Shape 표면 재구성 진행 중... (Alpha 값: {self.alpha_size})")
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd_clean, self.alpha_size)

        # 2단계: 메쉬 표면 매끄럽게 다듬기 (Taubin Smoothing)
        print("✨ 4. 표면 매끄럽게 다리미질 중 (Taubin Smoothing)...")
        mesh = mesh.filter_smooth_taubin(number_of_iterations=15)

        print("✨ 5. 법선(Normal) 벡터 계산 및 빛 반사 다듬기...")
        mesh.compute_vertex_normals()

        print(f"💾 6. 메쉬 저장 중: '{self.output_obj_path}'")
        o3d.io.write_triangle_mesh(self.output_obj_path, mesh)

    def extract_voxels(self, mesh_path, voxel_size=0.01):
        if not os.path.exists(mesh_path):
            print(f"❌ '{mesh_path}' 파일을 찾을 수 없습니다.")
            return

        print(f"📥 1. 메쉬 로드 중...")
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        mesh.compute_vertex_normals()
        
        vertices = np.asarray(mesh.vertices)
        normals = np.asarray(mesh.vertex_normals)
        
        # --- 물체의 실제 크기(Bounding Box) 확인 ---
        min_b = np.min(vertices, axis=0)
        max_b = np.max(vertices, axis=0)
        size = max_b - min_b
        print(f"📏 물체 크기: 가로 {size[0]:.4f}m, 세로 {size[1]:.4f}m, 높이 {size[2]:.4f}m")
        
        print(f"🧊 2. 완벽한 3D 바둑판 공간 생성 중... (간격: {voxel_size}m)")
        x_vals = np.arange(min_b[0], max_b[0], voxel_size)
        y_vals = np.arange(min_b[1], max_b[1], voxel_size)
        z_vals = np.arange(min_b[2], max_b[2], voxel_size)
        
        xx, yy, zz = np.meshgrid(x_vals, y_vals, z_vals)
        grid_points = np.vstack([xx.ravel(), yy.ravel(), zz.ravel()]).T
        
        print(f"🔍 3. 물체 표면(껍질)에 해당하는 점만 필터링 중...")
        tree = cKDTree(vertices)
        distances, indices = tree.query(grid_points, k=1)
        
        # 표면에 가까운 점만 남기기 (voxel_size 간격이므로 절대 뭉치지 않음)
        threshold = voxel_size * 0.8 
        valid_mask = distances < threshold
        
        surface_grid_points = grid_points[valid_mask]
        surface_normals = normals[indices[valid_mask]] # 해당 점의 표면 방향(법선)
        
        # 웹 UI에서 바로 띄워볼 수 있도록 기존 valid_grasps 포맷으로 임시 저장
        # (1단계이므로 폭(width)은 0, p1과 p2는 tcp와 동일하게 설정)
        dummy_grasps = []
        for i in range(len(surface_grid_points)):
            px, py, pz = surface_grid_points[i]
            nx, ny, nz = surface_normals[i]
            dummy_grasps.append({
                "tcp_x": round(float(px), 4),
                "tcp_y": round(float(py), 4),
                "tcp_z": round(float(pz), 4),
                "width": 0.0,
                "p1_x": round(float(px), 4), "p1_y": round(float(py), 4), "p1_z": round(float(pz), 4),
                "p2_x": round(float(px), 4), "p2_y": round(float(py), 4), "p2_z": round(float(pz), 4),
                "approach_dx": round(float(nx), 4),
                "approach_dy": round(float(ny), 4),
                "approach_dz": round(float(nz), 4)
            })
            
        with open(self.output_json_path, 'w') as f:
            json.dump({"valid_grasps": dummy_grasps}, f, indent=4)
            
        print(f"✅ 완료! '{self.output_json_path}'에 데이터가 저장되었습니다.")

    def process_all(self):
        self.load_and_meshify()
        self.extract_voxels(self.output_obj_path)
        return self.output_json_path