import os
import json
import open3d as o3d
import numpy as np
from scipy.spatial import cKDTree

class PointCloudProcessor:
    def __init__(self, ply_path, output_json_path, voxel_size=0.05, alpha_size=0.02):
        self.ply_path = ply_path
        self.output_json_path = output_json_path
        self.voxel_size = voxel_size
        self.alpha_size = alpha_size
        self.mesh = None
        self.voxel_points = None

    def load_and_meshify(self):
        if not os.path.exists(self.ply_path):
            print(f"❌ '{self.ply_path}' 파일을 찾을 수 없습니다.")
            return

        print(f"📥 1. 포인트 클라우드 로드 중: '{self.ply_path}'")
        pcd = o3d.io.read_point_cloud(self.ply_path)

        # 🌟 [추가됨] 1단계: 주변 노이즈(먼지) 제거
        print("🧹 2. 주변 노이즈(Outlier) 통계적 제거 중...")
        # nb_neighbors: 뭉쳐있는지 판단할 주변 점의 개수
        # std_ratio: 낮을수록 더 엄격하게 많이 지우고, 높을수록 관대하게 남깁니다. (1.0~2.0 추천)
        pcd_clean, ind = pcd.remove_statistical_outlier(nb_neighbors=40, std_ratio=1.0)
        
        # 노이즈가 제거된 깔끔한 포인트 클라우드만 선택
        pcd_clean = pcd.select_by_index(ind)

        print(f"🕸️ 3. Alpha Shape 표면 재구성 진행 중... (Alpha 값: {self.alpha_size})")
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd_clean, self.alpha_size)

        # 🌟 [추가됨] 2단계: 메쉬 표면 매끄럽게 다듬기 (Taubin Smoothing)
        print("✨ 4. 표면 매끄럽게 다리미질 중 (Taubin Smoothing)...")
        # number_of_iterations: 다리미질을 몇 번 할 것인가. (10~20 정도면 충분히 부드러워집니다)
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
        self.extract_voxels()
        return self.output_json_path