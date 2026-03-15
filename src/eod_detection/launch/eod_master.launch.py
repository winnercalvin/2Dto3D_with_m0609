import os
from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable, TimerAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder

def generate_launch_description():
    env_pytorch = SetEnvironmentVariable('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    env_openai = SetEnvironmentVariable('OPENAI_API_KEY', 'PUT_YOUR_OPENAI_API_KEY') 

    # 1. 로봇 & MoveIt 브링업
    moveit_config_dir = get_package_share_directory('m0609_with_rg2_moveit_config')
    robot_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(moveit_config_dir, 'launch', 'bringup_moveit.launch.py')
        ),
        launch_arguments={
            'mode': 'real',
            'host': '192.168.1.100',
            'port': '12345',
            'model': 'm0609'
        }.items()
    )

    # 2. 파라미터 세팅
    my_robot_desc_path = os.path.join(
        get_package_share_directory('my_robot_description'),
        'urdf',
        'm0609_with_rg2.urdf.xacro'
    )

    moveit_config = (
        MoveItConfigsBuilder("m0609_with_rg2", package_name="m0609_with_rg2_moveit_config")
        .robot_description(
            file_path=my_robot_desc_path,
            mappings={
                "mode": "real",
                "host": "192.168.1.100",
                "port": "12345",
                "update_rate": "100",
            }
        )
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .to_moveit_configs()
    )

    moveit_cpp_params = {
        "planning_pipelines": {"pipeline_names": ["ompl"]},
        "plan_request_params": {
            "planning_attempts": 1,
            "planning_pipeline": "ompl",
            "max_velocity_scaling_factor": 1.0,
            "max_acceleration_scaling_factor": 1.0,
        },
    }

    # 3. 커스텀 노드들 정의
    feature_node = Node(package='eod_detection', executable='feature_extractor_node', output='screen')
    analyzer_node = Node(package='eod_detection', executable='analyzer_node', output='screen')
    
    # 🔥🔥🔥 잃어버렸던 스캐너 노드 부활!!! 🔥🔥🔥
    scanner_node = Node(package='eod_detection', executable='scanner_node', output='screen')
    
    manipulator_node = Node(
        package='eod_detection', 
        executable='manipulator_node', 
        output='screen',
        parameters=[
            moveit_config.to_dict(),
            moveit_cpp_params
        ] 
    )

    # 4. 타이머 (스캐너 노드 실행 시간표 추가)
    delay_feature = TimerAction(period=8.0, actions=[feature_node])
    delay_scanner = TimerAction(period=12.0, actions=[scanner_node]) # 🔥 스캐너 12초에 투입!
    delay_analyzer = TimerAction(period=15.0, actions=[analyzer_node])
    delay_manipulator = TimerAction(period=20.0, actions=[manipulator_node])

    return LaunchDescription([
        env_pytorch,
        env_openai,
        robot_bringup,       
        delay_feature,     
        delay_scanner,       # 🔥 타이머에 등록
        delay_analyzer,      
        delay_manipulator    
    ])
