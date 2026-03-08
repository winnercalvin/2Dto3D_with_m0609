import open3d as o3d
import numpy as np
import json
import os
from datetime import datetime
from sklearn.cluster import KMeans

def extract_grasp_safe(mesh_path, output_json, num_samples=3):
    if not os.path.exists(mesh_path):
        print(f"❌ '{mesh_path}' 파일을 찾을 수 없습니다.")
        return

    print(f"📥 1. '{mesh_path}' 메쉬 로드 중...")
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # 🚨 Segfault 방지: 메쉬가 너무 비어있으면 중단
    if not mesh.has_triangles():
        print("❌ 메쉬 데이터가 비어있습니다. 메쉬 생성 단계를 다시 확인하세요.")
        return

    # 법선 벡터가 없으면 계산 (메쉬 수준에서의 계산은 안전합니다)
    mesh.compute_triangle_normals()

    # 🌟 핵심 해결책 1: 점만 뽑는 게 아니라 법선(Normals)도 같이 샘플링합니다. 
    # 이렇게 하면 pcd.estimate_normals()를 호출할 필요가 없어 터지지 않습니다!
    print("🎲 2. 메쉬 표면에서 점과 법선 벡터 샘플링 중...")
    pcd = mesh.sample_points_uniformly(number_of_points=1000, use_triangle_normal=True)
    
    points = np.asarray(pcd.points)
    normals = np.asarray(pcd.normals)

    # 🌟 핵심 해결책 2: 수동 방향 정렬 (NumPy 연산은 절대 안 터집니다)
    print("📐 3. 법선 벡터 수동 정렬 중...")
    camera_pos = np.array([0.0, 0.0, 0.0])
    for i in range(len(points)):
        view_dir = camera_pos - points[i]
        if np.dot(normals[i], view_dir) < 0:
            normals[i] = -normals[i]

    # 4. K-Means 클러스터링 (대표 구역 나누기)
    print(f"🎯 4. 가장 잡기 좋은 {num_samples}개 구역 찾는 중...")
    kmeans = KMeans(n_clusters=num_samples, random_state=42, n_init="auto")
    kmeans.fit(points)
    centroids = kmeans.cluster_centers_

    # 🌟 핵심 해결책 3: KDTree 대신 NumPy 브로드캐스팅으로 가장 가까운 점 찾기
    # (Open3D의 KDTreeFlann 라이브러리 충돌을 완벽히 회피합니다)
    final_grasp_points = []
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "target_mesh": os.path.abspath(mesh_path),
        "grasp_points": []
    }

    for i, center in enumerate(centroids):
        # 모든 점과 중심점 사이의 거리 계산 (NumPy 방식)
        dists = np.linalg.norm(points - center, axis=1)
        best_idx = np.argmin(dists)
        
        p = points[best_idx]
        n = normals[best_idx]
        
        output_data["grasp_points"].append({
            "score": 100.0,
            "position": { "x": round(float(p[0]), 5), "y": round(float(p[1]), 5), "z": round(float(p[2]), 5) },
            "approach_vector": { "nx": round(float(n[0]), 5), "ny": round(float(n[1]), 5), "nz": round(float(n[2]), 5) },
            "rank": i + 1
        })

    # 5. 저장
    with open(output_json, 'w') as f:
        json.dump(output_data, f, indent=4)
    
    print(f"🎉 성공! '{output_json}' 파일이 생성되었습니다.")

if __name__ == "__main__":
    # 파일 이름 확인! 아까 만든 structured_mesh.obj가 있는지 확인하세요.
    extract_grasp_safe("structured_mesh.obj", "mesh_grasp_points.json", num_samples=3)