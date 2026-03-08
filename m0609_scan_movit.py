import rclpy
from rclpy.node import Node
import math
import copy

# MoveIt 2 및 ROS 2 기본 메시지 임포트
from moveit_msgs.srv import GetPositionFK, GetCartesianPath
from moveit_msgs.msg import RobotState, PositionIKRequest
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Pose

class MoveIt2TrajectoryGenerator(Node):
    def __init__(self):
        super().__init__('moveit2_trajectory_generator')
        
        # 로봇 설정 (본인의 MoveIt 설정에 맞게 변경하세요)
        self.group_name = "arm"         # MoveIt 기구학 그룹 이름 (ex: manipulator, arm)
        self.end_effector_link = "link6" # 뎁스 카메라가 달린 끝단 링크 이름
        self.joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]

        # MoveIt 2 서비스 클라이언트
        self.fk_client = self.create_client(GetPositionFK, '/compute_fk')
        self.cartesian_client = self.create_client(GetCartesianPath, '/compute_cartesian_path')

        while not self.fk_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('MoveIt FK 서비스 대기 중...')
        while not self.cartesian_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('MoveIt Cartesian Path 서비스 대기 중...')

    def create_robot_state(self, joint_degrees):
        """Degree 배열을 Radian으로 변환하여 MoveIt용 RobotState를 생성합니다."""
        state = RobotState()
        js = JointState()
        js.name = self.joint_names
        js.position = [math.radians(deg) for deg in joint_degrees]
        state.joint_state = js
        return state

    def get_start_pose(self, joint_degrees):
        """현재 관절값을 기준으로 엔드 이펙터의 3D 공간 좌표(Pose)를 계산합니다."""
        req = GetPositionFK.Request()
        req.header.frame_id = "base_link"
        req.fk_link_names = [self.end_effector_link]
        req.robot_state = self.create_robot_state(joint_degrees)

        future = self.fk_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() and future.result().pose_stamped:
            # 반환된 3D 좌표 및 쿼터니언 자세
            return future.result().pose_stamped[0].pose
        else:
            self.get_logger().error("FK 계산 실패!")
            return None

    def compute_cartesian_path(self, start_joint_degrees, target_waypoints):
        """Z축과 자세를 고정한 채 X,Y 이동 궤적의 관절값 배열을 생성합니다."""
        req = GetCartesianPath.Request()
        req.header.frame_id = "base_link"
        req.group_name = self.group_name
        req.start_state = self.create_robot_state(start_joint_degrees)
        req.waypoints = target_waypoints
        
        # 세밀도 및 안정성 설정 (Meters 단위)
        req.max_step = 0.01      # 1cm 단위로 쪼개서 정밀하게 IK 계산
        req.jump_threshold = 1.5 # 관절이 갑자기 튀는 현상(Singularity) 방지
        req.avoid_collisions = True # (옵션) 장애물 회피 적용

        future = self.cartesian_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        response = future.result()
        if response and response.fraction > 0.9: # 궤적의 90% 이상 생성 성공 시
            self.get_logger().info(f"성공률: {response.fraction * 100:.1f}%")
            return response.solution.joint_trajectory.points
        else:
            self.get_logger().error(f"Cartesian Path 계산 실패 (성공률: {response.fraction if response else 0})")
            return None


def main(args=None):
    rclpy.init(args=args)
    generator = MoveIt2TrajectoryGenerator()

    # 1. 기준 시작점 (Degree)
    base_start_joint = [1.49, 41.28, 132.716, 182.946, 81.266, -87.036]
    
    # 2. 시작점의 3D 좌표(Pose) 가져오기
    start_pose = generator.get_start_pose(base_start_joint)
    if not start_pose:
        return

    generator.get_logger().info(f"시작 Z 높이: {start_pose.position.z:.3f}m")

    # 3. 목표 웨이포인트(Pose) 설정 (Z축 깊이 및 회전값 강제 고정)
    waypoints = []
    
    # 예시: 시작점에서 X축으로 20cm(0.2m), Y축으로 10cm(0.1m) 이동
    target_pose = copy.deepcopy(start_pose)
    target_pose.position.x += 0.20 
    target_pose.position.y += 0.10 
    # target_pose.position.z는 건드리지 않음 (높이 고정)
    # target_pose.orientation은 건드리지 않음 (카메라 평행 고정)
    
    waypoints.append(target_pose)

    # 4. MoveIt 2 궤적 생성
    trajectory_points = generator.compute_cartesian_path(base_start_joint, waypoints)

    if trajectory_points:
        print("\n================ [ MoveIt 2 동적 생성 웨이포인트 ] ================\n")
        print("MOVEIT_WAYPOINTS = [")
        
        # 일정한 간격으로 포인트를 뽑아내기 위해 스텝 조절 (너무 많으면 로봇 딜레이 발생)
        # 예: 10개 단위로 건너뛰며 출력
        step_size = max(1, len(trajectory_points) // 20) 
        
        for i in range(0, len(trajectory_points), step_size):
            pt = trajectory_points[i]
            # Radian을 다시 Degree로 변환
            deg_joints = [round(math.degrees(rad), 3) for rad in pt.positions]
            print(f"    {deg_joints},")
            
        # 마지막 도착점 보장
        if len(trajectory_points) - 1 % step_size != 0:
            last_pt = trajectory_points[-1]
            deg_joints = [round(math.degrees(rad), 3) for rad in last_pt.positions]
            print(f"    {deg_joints},")
            
        print("]")
        print("\n======================================================================\n")

    generator.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()