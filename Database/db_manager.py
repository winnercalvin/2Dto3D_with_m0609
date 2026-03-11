import os
import db_manager # 파일명 확인 (db_manager.py 인지)

def start_new_mission():
    try:
        db = db_manager.DBManager()
        
        # 1. DB 미션 생성
        mission_id = db.create_mission()
        
        home_path = os.path.expanduser("~")
        mission_dir = os.path.join(home_path, "robot_share", f"mission_{mission_id:03d}")
        
        sub_folders = ['raw', 'masked', 'features', '3dgs', 'output']
        
        # 2. 상위 미션 폴더부터 생성 및 권한 부여
        os.makedirs(mission_dir, exist_ok=True)
        os.chmod(mission_dir, 0o777) # 부모 폴더도 권한 부여
        
        for folder in sub_folders:
            path = os.path.join(mission_dir, folder)
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o777) 
        
        print(f"✅ Mission {mission_id:03d} 생성 완료: {mission_dir}")
        return mission_id, mission_dir

    except Exception as e:
        print(f"❌ 미션 생성 중 에러 발생: {e}")
        return None, None