import os
import db_manager  # 같은 폴더의 db_manager.py를 불러옵니다.

def start_new_mission():
    """
    새로운 로봇 미션을 생성하고, 공유 폴더 내에 필요한 데이터 구조를 구축합니다.
    """
    try:
        # 1. DB 매니저 초기화 및 미션 생성
        db = db_manager.DBManager()
        mission_id = db.create_mission()
        
        if mission_id is None:
            raise Exception("DB에서 미션 ID를 생성하지 못했습니다.")

        # 2. 경로 설정 (MSI/리전 공용: ~/robot_share/mission_XXX)
        home_path = os.path.expanduser("~")
        mission_dir = os.path.join(home_path, "robot_share", f"mission_{mission_id:03d}")
        
        # 3. 생성할 하위 폴더 리스트
        sub_folders = ['raw', 'masked', 'features', '3dgs', 'output']
        
        # 4. 상위 미션 폴더 생성 및 권한 부여 (777)
        # NFS 환경에서 클라이언트(Legion)의 쓰기 권한을 위해 777 설정이 필수입니다.
        os.makedirs(mission_dir, exist_ok=True)
        os.chmod(mission_dir, 0o777) 
        
        # 5. 하위 폴더들 생성 및 권한 부여
        for folder in sub_folders:
            path = os.path.join(mission_dir, folder)
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o777) 
        
        print(f"✅ [SUCCESS] Mission {mission_id:03d} 준비 완료")
        print(f"📂 경로: {mission_dir}")
        
        return mission_id, mission_dir

    except Exception as e:
        print(f"❌ [ERROR] 미션 생성 중 에러 발생: {e}")
        return None, None

# 만약 이 파일만 단독으로 실행했을 때 테스트로 한 번 돌려보고 싶다면 아래 주석을 해제하세요.
# if __name__ == "__main__":
#     start_new_mission()