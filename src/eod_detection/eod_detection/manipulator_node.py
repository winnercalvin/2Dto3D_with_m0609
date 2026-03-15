import os
import sys
import time
import math
import numpy as np
import rclpy
from rclpy.node import Node

# 🔥 String 대신 Float64MultiArray 임포트
from std_msgs.msg import Float64MultiArray 
from geometry_msgs.msg import PoseStamped, Pose
from moveit.planning import MoveItPy, PlanRequestParameters
from moveit_msgs.msg import CollisionObject
from shape_msgs.msg import SolidPrimitive
from scipy.spatial.transform import Rotation as R

from eod_detection.onrobot import RG

class ManipulatorNode(Node):
    def __init__(self):
        super().__init__('manipulator_node')
        self.get_logger().info("⏳ MoveItPy 초기화 중...")

        self.moveit = MoveItPy(node_name="manipulator_moveit_node")
        self.planning_group_name = "arm"
        
        # 성공했던 테스트 코드와 완벽하게 똑같은 기준점으로 롤백
        self.end_effector_link = "onrobot_rg2_base_link" 
        self.base_frame = "base_link"

        self.planning_component = self.moveit.get_planning_component(self.planning_group_name)
        self.collision_pub = self.create_publisher(CollisionObject, '/collision_object', 10)
        time.sleep(1.0) 

        self.spawn_desk() 

        self.get_logger().info("🗜️ 그리퍼(RG2) Modbus(192.168.1.1) 연결 시도 중...")
        try:
            self.gripper = RG("rg2", "192.168.1.1", 502)
            self.get_logger().info("✅ 그리퍼 연결 성공!")
        except Exception as e:
            self.get_logger().error(f"❌ 그리퍼 연결 실패: {e}")
            self.gripper = None

        # 🔥 구독자 타입 변경: String -> Float64MultiArray
        self.target_sub = self.create_subscription(Float64MultiArray, '/target_point', self.target_callback, 10)

    def spawn_desk(self):
        obj = CollisionObject()
        obj.header.frame_id = self.base_frame
        obj.id = "my_desk"
        primitive = SolidPrimitive()
        primitive.type = SolidPrimitive.BOX
        primitive.dimensions = [1.0, 2.0, 1.0]
        pose = Pose()
        pose.position.x = 0.32
        pose.position.y = 0.0
        pose.position.z = -0.505  
        pose.orientation.w = 1.0 
        obj.primitives.append(primitive)
        obj.primitive_poses.append(pose)
        obj.operation = CollisionObject.ADD
        self.collision_pub.publish(obj)

    def move_to_joint(self, j_deg, step_name):
        self.get_logger().info(f"🚀 [{step_name}] 이동 중... 목표 각도: {j_deg}")
        j_rad = [math.radians(x) for x in j_deg]
        
        plan_params = PlanRequestParameters(self.moveit)
        plan_params.max_velocity_scaling_factor = 0.1 # 10%로 안정성 극대화
        plan_params.max_acceleration_scaling_factor = 0.1
        plan_params.planning_time = 10.0
        
        self.planning_component.set_start_state_to_current_state()
        robot_state = self.planning_component.get_start_state()
        robot_state.set_joint_group_positions(self.planning_group_name, j_rad)
        self.planning_component.set_goal_state(robot_state=robot_state)
        
        plan_result = self.planning_component.plan(plan_params)
        if plan_result:
            self.moveit.execute(self.planning_group_name, plan_result.trajectory)
            self.get_logger().info(f"✅ [{step_name}] 도달 완료!")
            time.sleep(1.0)
        else:
            self.get_logger().error(f"❌ [{step_name}] 경로 계획 실패")

    # 🔥 콜백 함수 전면 수정: JSON 파일 대신 들어온 배열 데이터 직접 처리
    def target_callback(self, msg):
        # 배열 길이가 6 (x, y, z, Rx, Ry, Rz)인지 확인
        if len(msg.data) < 6:
            self.get_logger().error(f"❌ 잘못된 데이터 형식입니다. 데이터 길이: {len(msg.data)}")
            return

        t_x, t_y, t_z, rx, ry, rz = msg.data[:6]

        plan_params = PlanRequestParameters(self.moveit)
        plan_params.max_velocity_scaling_factor = 0.1 # 10% 속도
        plan_params.max_acceleration_scaling_factor = 0.1
        plan_params.planning_time = 10.0

        target_pose = PoseStamped()
        target_pose.header.frame_id = self.base_frame
        
        # 1. 위치(Position) 적용
        target_pose.pose.position.x = t_x
        target_pose.pose.position.y = t_y
        target_pose.pose.position.z = t_z
        
        # 2. 자세(Orientation) 적용: Euler (Rx, Ry, Rz) -> Quaternion 변환
        # ⚠️ 중요: 3DGS 쪽에서 보내는 각도가 'Degree(도)' 단위라고 가정하고 degrees=True 로 설정했습니다.
        # 만약 3DGS 쪽에서 'Radian(라디안)'으로 보낸다면 degrees=False 로 변경해 주세요.
        r = R.from_euler('xyz', [rx, ry, rz], degrees=True)
        qx, qy, qz, qw = r.as_quat()

        target_pose.pose.orientation.x = qx
        target_pose.pose.orientation.y = qy
        target_pose.pose.orientation.z = qz
        target_pose.pose.orientation.w = qw

        self.get_logger().info(f"🎯 [1. 목표물 접근] 타겟 좌표: X={t_x:.3f}, Y={t_y:.3f}, Z={t_z:.3f} | 회전: Rx={rx:.1f}, Ry={ry:.1f}, Rz={rz:.1f}")

        self.planning_component.set_start_state_to_current_state()
        robot_state = self.planning_component.get_start_state()
        ik_success = robot_state.set_from_ik(self.planning_group_name, target_pose.pose, self.end_effector_link, timeout=2.0)

        if ik_success:
            self.planning_component.set_goal_state(robot_state=robot_state)
            plan_result = self.planning_component.plan(plan_params)

            if plan_result:
                self.get_logger().warn("🚀 1. 목표물(Pick) 위치로 이동!")
                self.moveit.execute(self.planning_group_name, plan_result.trajectory)
                time.sleep(1.0)
                
                if self.gripper:
                    self.get_logger().info("🗜️ 2. >>> [그리퍼] 물건 꽉 쥐기 (Close)!")
                    self.gripper.close_gripper(force_val=400)
                    time.sleep(1.5)
                
                drop_j = [-31.15, 67.78, 27.55, 62.70, 91.57, -55.76]
                self.move_to_joint(drop_j, "3. 물건 놓기(Drop) 위치")
                
                if self.gripper:
                    self.get_logger().info("🗜️ 4. >>> [그리퍼] 물건 놓기 (Open)!")
                    self.gripper.open_gripper(force_val=400)
                    time.sleep(1.5)
                    
                home_j = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
                self.move_to_joint(home_j, "5. 홈(Home) 복귀")
                
                self.get_logger().warn("🎉 임무 완수! 시스템을 대기 상태로 유지합니다.")
                # sys.exit(0)  # 연속 동작을 위해 주석 처리 (원하시면 다시 활성화하세요)
            else:
                self.get_logger().error("❌ 경로 계획 실패")
        else:
            self.get_logger().error("❌ IK 변환 실패")

def main(args=None):
    rclpy.init(args=args)
    node = ManipulatorNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        node.get_logger().info("성공적으로 프로그램이 종료되었습니다.")
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()