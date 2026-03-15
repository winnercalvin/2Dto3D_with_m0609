import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # ⚠️ 여기에 본인의 ROS 2 패키지 이름을 적어주세요!
    package_name = '3dgs_pkg'

    # 1. PLY -> OBJ 자동 변환 노드
    ply_to_obj_node = Node(
        package=package_name,
        executable='ply_to_obj_node',
        name='ply_to_obj_node',
        output='screen', # 터미널에 로그를 바로 출력
        emulate_tty=True # 로그 색상 지원
    )

    # 2. Whisper 기반 STT (음성 인식) 노드
    whisper_stt_node = Node(
        package=package_name,
        executable='whisper_stt_node',
        name='whisper_stt_node',
        output='screen',
        emulate_tty=True
    )
    # 3. 🔥 새롭게 추가된 Feature 학습 노드
    feature_train_node = Node(
        package=package_name,
        executable='feature',  # setup.py에 등록하신 'feature' 이름 사용
        name='feature_train_node',
        output='screen',
        emulate_tty=True
    )

    # LaunchDescription에 실행할 노드들을 담아서 반환
    return LaunchDescription([
        ply_to_obj_node,
        whisper_stt_node,
        feature_train_node
    ])