# test_starter.py
from mission_starter import start_new_mission
import os

print("🔍 [TEST] 미션 생성 및 폴더 구축 테스트 시작...")

# 1. 함수 실행
m_id, m_path = start_new_mission()

# 2. 결과 검증
if m_id is not None:
    print(f"\n✅ 1. DB 연결 성공! 생성된 미션 ID: {m_id}")
    print(f"✅ 2. 폴더 경로 생성 성공: {m_path}")
    
    # 실제 폴더들이 다 생겼는지 확인
    expected_folders = ['raw', 'masked', 'features', '3dgs', 'output']
    all_exist = True
    
    print("\n📂 폴더 생성 상세 내역:")
    for sub in expected_folders:
        full_sub_path = os.path.join(m_path, sub)
        if os.path.exists(full_sub_path):
            # 권한(Permission)도 777인지 확인 (8진수 출력)
            mode = oct(os.stat(full_sub_path).st_mode)[-3:]
            print(f"  - {sub}/ : 존재함 (권한: {mode})")
        else:
            print(f"  - {sub}/ : ❌ 생성 실패")
            all_exist = False
            
    if all_exist:
        print("\n🎉 모든 테스트를 통과했습니다! 이제 AI 동작 코드에 합쳐도 됩니다.")
else:
    print("\n❌ 테스트 실패: DB 연동이나 폴더 생성에 문제가 있습니다. 에러 메시지를 확인하세요.")