import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
import math
import time
import sys

# 🔥 질문자님의 onrobot.py를 정확히 불러옵니다!
try:
    from onrobot import RG
except ImportError:
    print("🚨 [에러] 'onrobot.py' 파일을 찾을 수 없습니다!")
    sys.exit(1)

class StandalonePnPNode(Node):
    def __init__(self):
        super().__init__('standalone_pnp_node')
        
        # 로봇 팔 제어기
        self.traj_client = ActionClient(self, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
        
        self.get_logger().info("🗜️ 그리퍼(RG2) Modbus(192.168.1.1) 연결 시도 중...")
        try:
            self.gripper = RG("rg2", "192.168.1.1", 502)
            self.get_logger().info("✅ 그리퍼 연결 성공!")
        except Exception as e:
            self.get_logger().error(f"❌ 그리퍼 연결 실패: {e}")
            self.gripper = None

    def move_arm(self, j_deg, step_name, duration=5.0):
        self.get_logger().info(f"🚀 [{step_name}] 이동 중... 목표: {j_deg}")
        
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6']
        
        point = JointTrajectoryPoint()
        point.positions = [math.radians(x) for x in j_deg]
        point.time_from_start.sec = int(duration)
        point.time_from_start.nanosec = int((duration % 1) * 1e9)
        goal_msg.trajectory.points.append(point)
        
        self.traj_client.wait_for_server()
        send_goal_future = self.traj_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f"❌ [{step_name}] 로봇 이동 거부됨!")
            return
            
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        self.get_logger().info(f"✅ [{step_name}] 도달 완료!")
        time.sleep(1.0) 

    def grip(self):
        self.get_logger().info("🗜️ >>> [그리퍼] 물건 꽉 쥐기 (Close)!")
        if self.gripper:
            try:
                self.gripper.close_gripper(force_val=400) # 최대 힘으로 닫기
                time.sleep(1.5)
            except Exception as e:
                self.get_logger().error(f"그리퍼 조작 실패: {e}")

    def release(self):
        self.get_logger().info("🗜️ >>> [그리퍼] 물건 놓기 (Open)!")
        if self.gripper:
            try:
                self.gripper.open_gripper(force_val=400) # 완전히 열기
                time.sleep(1.5)
            except Exception as e:
                self.get_logger().error(f"그리퍼 조작 실패: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = StandalonePnPNode()

    # ========================================================
    # 🎯 Pick & Place 시나리오 시작
    # ========================================================
    
    # 1. 타겟 1번 위치(Pick)로 이동
    pick_j = [-17.00, 37.93, 78.83, 59.48, 41.09, -32.89]
    node.move_arm(pick_j, "1. 물건 잡기(Pick)", duration=6.0)

    # 2. 그리퍼 꽉 닫기!
    node.grip()

    # 3. 타겟 2번 위치(Drop)로 이동
    drop_j = [-28.77, 54.05, 58.76, 69.72, 74.95, -44.74]
    node.move_arm(drop_j, "2. 물건 놓기(Drop)", duration=6.0)

    # 4. 그리퍼 열기!
    node.release()

    # 5. 홈 위치로 복귀
    home_j = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
    node.move_arm(home_j, "3. 홈(Home) 복귀", duration=5.0)
    
    node.get_logger().info("🎉 초고속 Pick & Place 테스트 완료!")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
