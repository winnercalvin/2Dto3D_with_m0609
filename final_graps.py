import json
import numpy as np
import os
from datetime import datetime

def find_true_pineapple_midpoint(input_json, output_json):
    if not os.path.exists(input_json):
        print(f"❌ '{input_json}' 파일이 없습니다.")
        return

    with open(input_json, 'r') as f:
        data = json.load(f)
    
    points_data = data['grasp_points']
    if len(points_data) < 2:
        print("❌ 분석할 점이 너무 적습니다! voxel_size를 더 줄여서 실행하세요.")
        return

    points = np.array([[p['position']['x'], p['position']['y'], p['position']['z']] for p in points_data])
    normals = np.array([[p['approach_vector']['nx'], p['approach_vector']['ny'], p['approach_vector']['nz']] for p in points_data])

    # 1. 잎사귀 제거 (Z축 ROI 필터) - 더 정교하게
    z_min, z_max = np.min(points[:, 2]), np.max(points[:, 2])
    body_mask = (points[:, 2] < z_min + (z_max - z_min) * 0.6) # 상위 40%는 무조건 잎사귀로 간주
    f_points = points[body_mask]
    f_normals = normals[body_mask]

    # 2. 물체의 수직 중심축(Average X, Y) 계산
    # 이게 바로 파인애플의 '심지' 위치입니다.
    center_axis_xy = np.mean(f_points[:, :2], axis=0)
    print(f"📍 파인애플 중심축 감지: X={center_axis_xy[0]:.2f}, Y={center_axis_xy[1]:.2f}")

    all_candidates = []
    
    # 전략 A: 마주보는 쌍(Pair) 검색 (조건을 아주 많이 완화함)
    for i in range(len(f_points)):
        for j in range(i + 1, len(f_points)):
            p1, p2 = f_points[i], f_points[j]
            n1, n2 = f_normals[i], f_normals[j]
            dist = np.linalg.norm(p1 - p2)

            # 파인애플 지름 범위 (데이터가 mm라면 40~130, m라면 0.04~0.13)
            # 여기서는 유저님 데이터인 mm 기준으로 설정
            if 40.0 < dist < 150.0: 
                cos_theta = np.dot(n1, n2)
                if cos_theta < -0.3: # 대략적으로만 마주 봐도 통과!
                    midpoint = (p1 + p2) / 2.0
                    all_candidates.append({
                        "pos": midpoint,
                        "norm": (n1 - n2) / 2.0,
                        "width": dist,
                        "score": (1.0 - cos_theta) * 100
                    })

    # 전략 B: 만약 쌍이 하나도 없으면? 표면 점들을 중심축으로 밀어넣기
    if len(all_candidates) == 0:
        print("⚠️ 마주보는 쌍이 없어 '가상 중심 투사' 모드로 전환합니다.")
        for i in range(len(f_points)):
            # 표면 점 p1에서 중심축 방향으로 이동한 지점을 파지점으로 설정
            projected_pos = np.array([center_axis_xy[0], center_axis_xy[1], f_points[i][2]])
            all_candidates.append({
                "pos": projected_pos,
                "norm": f_normals[i],
                "width": 80.0, # 기본 너비 설정
                "score": 50.0
            })

    # 점수순 정렬 및 저장
    all_candidates = sorted(all_candidates, key=lambda x: x['score'], reverse=True)
    
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "grasp_points": []
    }

    # 중복 제거를 위해 높이(Z)가 비슷한 점들은 하나만 남김
    final_picks = []
    for cand in all_candidates:
        if not any(abs(cand['pos'][2] - p['pos'][2]) < 10.0 for p in final_picks):
            final_picks.append(cand)
        if len(final_picks) >= 5: break

    for k, p in enumerate(final_picks):
        n_vec = p['norm'] / np.linalg.norm(p['norm'])
        output_data["grasp_points"].append({
            "score": round(p['score'], 2),
            "position": { "x": round(p['pos'][0], 4), "y": round(p['pos'][1], 4), "z": round(p['pos'][2], 4) },
            "approach_vector": { "nx": round(n_vec[0], 4), "ny": round(n_vec[1], 4), "nz": round(n_vec[2], 4) },
            "gripper_width": round(p['width'], 2),
            "rank": k + 1
        })

    with open(output_json, 'w') as f:
        json.dump(output_data, f, indent=4)

    print(f"🎉 최종 완료! '{output_json}'에 파인애플 관통 중간점 {len(output_data['grasp_points'])}개 생성.")

if __name__ == "__main__":
    find_true_pineapple_midpoint("structured_voxel_grasp.json", "final_center_grasps.json")