import open3d as o3d
import numpy as np
import json
import os

def mesh_to_structured_voxels(mesh_path, output_json, voxel_size=10.0):
    if not os.path.exists(mesh_path):
        print(f"❌ '{mesh_path}' 파일을 찾을 수 없습니다.")
        return

    print(f"📥 1. '{mesh_path}' 메쉬 로드 중...")
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # 2. 메쉬 표면에서 아주 촘촘하게 점들을 먼저 샘플링합니다.
    # 복셀화하기 전에 충분한 데이터를 확보하기 위함입니다.
    print("🎲 2. 메쉬 표면 샘플링 중...")
    pcd = mesh.sample_points_uniformly(number_of_points=50000, use_triangle_normal=True)

    # 3. Voxel Downsampling (정형화 핵심)
    # 지정한 voxel_size 간격의 격자마다 딱 하나의 점만 남깁니다.
    print(f"🧊 3. 복셀화 진행 중... (격자 크기: {voxel_size}mm)")
    voxel_pcd = pcd.voxel_down_sample(voxel_size=voxel_size)
    
    # 4. 법선 벡터 수동 정렬 (맥북 Segfault 방지 안전 모드)
    points = np.asarray(voxel_pcd.points)
    normals = np.asarray(voxel_pcd.normals)
    camera_pos = np.array([0.0, 0.0, 0.0])

    for i in range(len(points)):
        view_dir = camera_pos - points[i]
        if np.dot(normals[i], view_dir) < 0:
            normals[i] = -normals[i]

    # 5. JSON 데이터 생성
    voxel_data = []
    for i in range(len(points)):
        voxel_data.append({
            "x": round(float(points[i][0]), 4),
            "y": round(float(points[i][1]), 4),
            "z": round(float(points[i][2]), 4),
            "nx": round(float(normals[i][0]), 4),
            "ny": round(float(normals[i][1]), 4),
            "nz": round(float(normals[i][2]), 4)
        })

    with open(output_json, 'w') as f:
        json.dump({"voxels": voxel_data}, f, indent=4)

    print(f"✅ 완료! {len(points)}개의 정형화된 복셀 데이터가 '{output_json}'에 저장되었습니다.")
    
    # 시각적으로 확인하고 싶다면 아래 주석 해제
    # o3d.visualization.draw_geometries([voxel_pcd])

if __name__ == "__main__":
    # structured_mesh.obj를 10mm(1cm) 단위 복셀로 변환
    mesh_to_structured_voxels("structured_mesh.obj", "structured_voxel_data.json", voxel_size=10.0)