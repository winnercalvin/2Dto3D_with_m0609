import open3d as o3d
import numpy as np
import json
import os
from datetime import datetime

def mesh_to_voxel_grasp_format(mesh_path, output_json, voxel_size=10.0):
    if not os.path.exists(mesh_path):
        print(f"❌ '{mesh_path}' 파일을 찾을 수 없습니다.")
        return

    print(f"📥 1. '{mesh_path}' 메쉬 로드 중...")
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    mesh.compute_triangle_normals()

    # 2. 메쉬 표면에서 촘촘하게 샘플링 (복셀의 소스가 될 점들)
    print("🎲 2. 메쉬 표면 샘플링 중...")
    pcd = mesh.sample_points_uniformly(number_of_points=100000, use_triangle_normal=True)

    # 3. Voxel Downsampling (정형화)
    print(f"🧊 3. 복셀화 진행 중... (격자 크기: {voxel_size}mm)")
    voxel_pcd = pcd.voxel_down_sample(voxel_size=voxel_size)
    
    # 4. 법선 벡터 수동 정렬 (Segfault 방지)
    points = np.asarray(voxel_pcd.points)
    normals = np.asarray(voxel_pcd.normals)
    camera_pos = np.array([0.0, 0.0, 0.0])

    for i in range(len(points)):
        view_dir = camera_pos - points[i]
        if np.dot(normals[i], view_dir) < 0:
            normals[i] = -normals[i]

    # 5. 요청하신 "grasp_points" 형태의 JSON 구조로 조립
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "target_mesh": os.path.abspath(mesh_path),
        "grasp_points": []
    }

    print(f"📝 4. {len(points)}개의 복셀을 파지점 포맷으로 변환 중...")
    for i in range(len(points)):
        output_data["grasp_points"].append({
            "score": 100.0, # 복셀 데이터는 모두 기본 점수 100점 부여
            "position": {
                "x": round(float(points[i][0]), 5),
                "y": round(float(points[i][1]), 5),
                "z": round(float(points[i][2]), 5)
            },
            "approach_vector": {
                "nx": round(float(normals[i][0]), 5),
                "ny": round(float(normals[i][1]), 5),
                "nz": round(float(normals[i][2]), 5)
            },
            "rank": i + 1
        })

    # 6. 파일 저장
    with open(output_json, 'w') as f:
        json.dump(output_data, f, indent=4)

    print(f"🎉 성공! 정형화된 복셀 JSON이 생성되었습니다: '{output_json}'")

if __name__ == "__main__":
    # structured_mesh.obj를 10mm 단위 복셀로 변환하여 동일 포맷으로 저장
    mesh_to_voxel_grasp_format("structured_mesh.obj", "structured_voxel_grasp.json", voxel_size=0.5)