import open3d as o3d
import numpy as np
import json
import os

def process_and_export_downsampled_pcd(ply_path, json_output_path, voxel_size=10.0):
    if not os.path.exists(ply_path):
        print(f"❌ '{ply_path}' 파일을 찾을 수 없습니다!")
        return None

    pcd = o3d.io.read_point_cloud(ply_path)
    pcd.remove_non_finite_points()

    print(f"🧊 Voxel Downsampling 진행 중... (큐브 크기: {voxel_size})")
    downpcd = pcd.voxel_down_sample(voxel_size=voxel_size)
    print(f"📉 다운샘플링 후 점 개수: {len(downpcd.points):,}개")

    print("📐 [1/2] 법선 벡터(Normals) 계산 시작...")
    downpcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamKNN(knn=15)
    )
    print("✅ [1/2] 계산 완료!")

    # ==========================================
    # 🌟 핵심 해결책: 버그 난 C++ 함수 대신 파이썬으로 직접 정렬!
    # ==========================================
    print("📐 [2/2] 안전한 NumPy 방식으로 법선 벡터 방향 정렬 시작...")
    
    points = np.asarray(downpcd.points)
    normals = np.asarray(downpcd.normals)
    camera_pos = np.array([0.0, 0.0, 0.0]) # 로봇 베이스 또는 카메라 원점

    # 각 점마다 카메라를 바라보는지 수학적으로(내적) 검사합니다.
    for i in range(len(points)):
        view_dir = camera_pos - points[i] # 점에서 카메라를 향하는 벡터
        # 내적(Dot product)이 음수면 법선이 반대(물체 안쪽)를 향한다는 뜻
        if np.dot(normals[i], view_dir) < 0:
            normals[i] = -normals[i] # 부호를 휙! 뒤집어줍니다.

    print("✅ [2/2] 정렬 완료! (Open3D 버그 완벽 회피 성공)")
    # ==========================================

    grasp_data = []
    for i in range(len(points)):
        grasp_data.append({
            "x": round(float(points[i][0]), 5),
            "y": round(float(points[i][1]), 5),
            "z": round(float(points[i][2]), 5),
            "nx": round(float(normals[i][0]), 5),
            "ny": round(float(normals[i][1]), 5),
            "nz": round(float(normals[i][2]), 5)
        })

    with open(json_output_path, 'w') as f:
        json.dump({"points": grasp_data}, f, indent=4)

    print(f"🎉 최종 완료! '{json_output_path}' 생성 성공!")
    return downpcd

if __name__ == "__main__":
    input_ply = "point_cloud.ply" 
    output_json = "downsampled_points.json" 
    
    process_and_export_downsampled_pcd(input_ply, output_json, voxel_size=0.5)