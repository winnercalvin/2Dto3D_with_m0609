import rclpy
from rclpy.node import Node
from moveit.planning import MoveItPy, PlanRequestParameters 
from geometry_msgs.msg import PoseStamped
from moveit_msgs.msg import Constraints, JointConstraint # 추가
import time
import math
from scipy.spatial.transform import Rotation as R

def euler_to_quaternion(rx_deg, ry_deg, rz_deg):
    r = R.from_euler('xyz', [rx_deg, ry_deg, rz_deg], degrees=True)
    x, y, z, w = r.as_quat()
    return x, y, z, w

def main(args=None):
    rclpy.init(args=args)
    moveit = MoveItPy(node_name="moveit_py_node")
    
    planning_group_name = "arm"
    end_effector_link = "onrobot_rg2_base_link" 
    
    planning_component = moveit.get_planning_component(planning_group_name)
    
    # 1. 목표 Pose 설정 (티치 펜던트 값)
    target_pose = PoseStamped()
    target_pose.header.frame_id = "base_link"
    target_pose.pose.position.x = 0.547
    target_pose.pose.position.y = -0.068
    target_pose.pose.position.z = 0.149
    
    qx, qy, qz, qw = euler_to_quaternion(13.56, 109.42, 39.05)
    target_pose.pose.orientation.x = qx
    target_pose.pose.orientation.y = qy
    target_pose.pose.orientation.z = qz
    target_pose.pose.orientation.w = qw

    # 2. 💡 IK로 기본 관절값 계산
    start_state = planning_component.get_start_state()
    ik_success = start_state.set_from_ik(planning_group_name, target_pose.pose, end_effector_link, timeout=2.0)

    if ik_success:
        print("✅ IK 계산 성공")
        joint_values = list(start_state.get_joint_group_positions(planning_group_name))
        
        # 💡 마지막 조인트(Joint 6)에 90도(1.5708 rad) 강제 가산
        joint_values[5] -= 0.5
        
        # 3. 💡 [수정 포인트] Constraints 객체를 생성하여 목표 설정
        joint_names = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]
        joint_constraints = []
        for name, value in zip(joint_names, joint_values):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = float(value)
            jc.tolerance_above = 0.001
            jc.tolerance_below = 0.001
            jc.weight = 1.0
            joint_constraints.append(jc)
            
        goal_constraints = Constraints()
        goal_constraints.joint_constraints = joint_constraints
        
        # 💡 생성한 제약 조건을 목표 상태로 지정 (리스트 형태로 넣어야 함)
        planning_component.set_goal_state(motion_plan_constraints=[goal_constraints])
        
        # 4. 경로 계획 및 실행
        plan_params = PlanRequestParameters(moveit)
        plan_params.max_velocity_scaling_factor = 0.1
        plan_params.max_acceleration_scaling_factor = 0.1
        plan_params.planner_id = "RRTConnect"

        print("🚀 90도 회전이 포함된 경로 계획 시작...")
        plan_result = planning_component.plan(plan_params)
        
        if plan_result:
            moveit.execute(planning_group_name, plan_result.trajectory)
            print("✨ 성공적으로 이동했습니다!")
        else:
            print("❌ 경로 계획 실패")
    else:
        print("❌ IK 계산 실패")

    rclpy.shutdown()

if __name__ == '__main__':
    main()