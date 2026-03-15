import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as RosImage, JointState # 🔥 현재 관절 위치를 읽기 위해 추가!
from std_msgs.msg import Bool 
from cv_bridge import CvBridge
import cv2
import os
import torch
import numpy as np
import time
import math 
from PIL import Image as PILImage
from ultralytics import YOLO

from transformers import AutoProcessor, AutoModelForCausalLM, PretrainedConfig
import transformers.dynamic_module_utils as dyn_utils
from unittest.mock import patch
from openai import OpenAI

from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint

# =========================================================
# 🎯 폭발물 탐색(Search)을 위한 3단계 '관절(Joint)' 좌표
# =========================================================
SEARCH_LEFT_POSJ = [57.50, -3.58, 129.61, 24.56, -24.61, 68.80]
SEARCH_CENTER_POSJ = [8.91, -7.22, 132.98, 20.53, -10.80, 69.01] 
SEARCH_RIGHT_POSJ = [-50.52, -1.45, 124.59, 7.92, -17.74, 84.63]

class EODAnalyzerNode(Node):
    def __init__(self):
        super().__init__('eod_analyzer_node')
        self.bridge = CvBridge()
        
        self.is_analyzing = False
        self.target_found = False
        self.captured_image = None
        self.target_classes = ['bomb', 'wire', 'battery']
        self.search_state = 0 
        self.last_move_time = time.time()
        
        self.detection_count = 0                 
        self.required_consecutive_frames = 10    
        self.bomb_min_area_ratio = 0.15          
        self.center_margin = 0.35               
        
        self.scan_trigger_pub = self.create_publisher(Bool, '/trigger_eod_scan', 10)
        self.traj_client = ActionClient(self, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
        self.active_goal_handle = None 
        
        # 🔥 [NEW] 로봇의 현재 위치를 실시간으로 저장할 변수 및 구독자
        self.current_joints = None
        self.joint_sub = self.create_subscription(JointState, '/joint_states', self.joint_callback, 10)
        
        self.get_logger().info("⏳ AI 모델들을 메모리에 로드합니다. 잠시만 기다려주세요...")
 
        self.yolo_model = YOLO('/home/rokey/EOD_ws/src/eod_detection/weights/YOLOv11n_add2.pt') 
        PretrainedConfig.forced_bos_token_id = None
        orig_get_imports = dyn_utils.get_imports
        def custom_get_imports(filename):
            imports = orig_get_imports(filename)
            if "flash_attn" in imports: imports.remove("flash_attn")
            return imports

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = "microsoft/Florence-2-base"
        with patch("transformers.dynamic_module_utils.get_imports", custom_get_imports):
            self.florence_model = AutoModelForCausalLM.from_pretrained(
                self.model_id, trust_remote_code=True, low_cpu_mem_usage=False, device_map=None
            ).cpu().eval()
            self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
            
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        self.subscription = self.create_subscription(RosImage, '/camera/camera/color/image_raw', self.image_callback, 10)
        self.get_logger().info("✅ YOLO 및 VLM 로드 완료! 카메라 감시를 시작합니다.")

        self.control_timer = self.create_timer(0.1, self.robot_control_loop)

    # =========================================================
    # 🤖 [NEW] 로봇 현재 관절 위치 실시간 업데이트
    # =========================================================
    def joint_callback(self, msg):
        try:
            joint_dict = dict(zip(msg.name, msg.position))
            self.current_joints = [
                joint_dict['joint_1'], joint_dict['joint_2'], joint_dict['joint_3'],
                joint_dict['joint_4'], joint_dict['joint_5'], joint_dict['joint_6']
            ]
        except Exception:
            pass

    # =========================================================
    # 🤖 [초특급 비기] 급가속/급발진 완벽 차단 밀집 궤적 생성기
    # =========================================================
    def send_joint_goal(self, j_deg, duration=8.0): 
        if self.current_joints is None:
            self.get_logger().warn("⏳ 로봇의 현재 위치를 파악 중입니다...")
            return

        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6']
        
        target_rad = [math.radians(x) for x in j_deg]
        
        # 🔥 8초의 시간을 30개의 구간으로 잘게 쪼갭니다 (제어기가 딴짓 못하게 못 박음)
        num_steps = 30 
        for step in range(1, num_steps + 1):
            t = step / float(num_steps)
            
            # 부드러운 S자 곡선(Smoothstep) 공식 적용: 서서히 출발하고 서서히 멈춤!
            ease = t * t * (3.0 - 2.0 * t) 
            
            point = JointTrajectoryPoint()
            interp_pos = []
            # 현재 위치에서 목표 위치까지 부드러운 비율로 계산
            for start, end in zip(self.current_joints, target_rad):
                interp_pos.append(start + (end - start) * ease)
            
            point.positions = interp_pos
            
            time_from_start = duration * t
            point.time_from_start.sec = int(time_from_start)
            point.time_from_start.nanosec = int((time_from_start % 1) * 1e9)
            
            goal_msg.trajectory.points.append(point)
        
        self.traj_client.wait_for_server()
        send_goal_future = self.traj_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('🚨 이동 명령이 거부되었습니다!')
            return
        self.active_goal_handle = goal_handle

    def halt_robot(self):
        if not self.target_found:
            self.target_found = True
            if self.active_goal_handle is not None:
                self.active_goal_handle.cancel_goal_async()
            self.get_logger().warn("🛑 락온 완료! 로봇 이동 취소(정지) 명령 하달!")

    # =========================================================
    # 🔄 심플 왕복 패트롤(순찰) 탐색 루프
    # =========================================================
    def robot_control_loop(self):
        if self.target_found or self.is_analyzing:
            return

        # 현재 로봇 위치를 모르면 출발하지 않고 대기합니다.
        if self.current_joints is None:
            return

        current_time = time.time()
        
        if self.search_state == 0:
            self.get_logger().info("🔎 [순찰] 왼쪽 끝 지점을 탐색합니다.")
            self.send_joint_goal(SEARCH_LEFT_POSJ, duration=8.0)
            self.search_state = 1
            self.last_move_time = current_time
            
        elif self.search_state == 1 and (current_time - self.last_move_time > 10.0):
            self.get_logger().info("🔎 [순찰] 중앙으로 이동합니다.")
            self.send_joint_goal(SEARCH_CENTER_POSJ, duration=8.0)
            self.search_state = 2
            self.last_move_time = current_time
                
        elif self.search_state == 2 and (current_time - self.last_move_time > 10.0):
            self.get_logger().info("🔎 [순찰] 오른쪽 끝 지점으로 탐색을 진행합니다.")
            self.send_joint_goal(SEARCH_RIGHT_POSJ, duration=8.0)
            self.search_state = 3
            self.last_move_time = current_time
                
        elif self.search_state == 3 and (current_time - self.last_move_time > 10.0):
            self.get_logger().info("🔎 [순찰 복귀] 다시 중앙으로 이동합니다.")
            self.send_joint_goal(SEARCH_CENTER_POSJ, duration=8.0)
            self.search_state = 4
            self.last_move_time = current_time

        elif self.search_state == 4 and (current_time - self.last_move_time > 10.0):
            self.get_logger().info("🔄 1회 왕복 순찰 완료. 이상 없음! 다시 왼쪽으로 방향을 틉니다.")
            self.search_state = 0 

    def image_callback(self, msg):
        if self.is_analyzing:
            return

        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        H, W = cv_image.shape[:2]
        
        results = self.yolo_model(cv_image, conf=0.85, verbose=False)
        detected_class_names = []
        bomb_boxes = [] 
        
        display_image = cv_image.copy()
        
        safe_x1, safe_y1 = int(W * self.center_margin), int(H * self.center_margin)
        safe_x2, safe_y2 = int(W * (1 - self.center_margin)), int(H * (1 - self.center_margin))
        
        cv2.rectangle(display_image, (safe_x1, safe_y1), (safe_x2, safe_y2), (255, 255, 0), 2)
        cv2.putText(display_image, "Safe Zone", (safe_x1, safe_y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = result.names[class_id]
                confidence = float(box.conf[0])
                
                detected_class_names.append(class_name)
                
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(display_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                label_text = f"{class_name} {confidence*100:.1f}%"
                cv2.putText(display_image, label_text, (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                            
                if class_name == 'bomb':
                    bomb_boxes.append((x1, y1, x2, y2))
        
        is_perfect_angle = False
        
        if all(tc in detected_class_names for tc in self.target_classes):
            for (bx1, by1, bx2, by2) in bomb_boxes:
                box_area = (bx2 - bx1) * (by2 - by1)
                img_area = W * H
                area_ratio = box_area / img_area
                
                cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
                
                if area_ratio >= self.bomb_min_area_ratio and (safe_x1 < cx < safe_x2) and (safe_y1 < cy < safe_y2):
                    is_perfect_angle = True
                    break

        if is_perfect_angle:
            self.detection_count += 1
            lock_text = f"LOCKING ON... {self.detection_count}/{self.required_consecutive_frames}"
            cv2.putText(display_image, lock_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            
            if self.detection_count >= self.required_consecutive_frames:
                self.halt_robot()
                self.is_analyzing = True
                self.detection_count = 0 
                
                self.get_logger().warn("🚨 위험 의심 물체 포착! VLM 정밀 판독을 시작합니다.")
                
                cv2.imshow("EOD Robot Camera", display_image)
                cv2.waitKey(1)
                
                rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                self.captured_image = PILImage.fromarray(rgb_image)
                return 
        else:
            self.detection_count = 0
            
        cv2.imshow("EOD Robot Camera", display_image)
        cv2.waitKey(1)

    def run_vlm_pipeline(self, image):
        self.get_logger().info("🔍 Florence-2: 이미지 상황 묘사 중...")
        task_prompt = "<MORE_DETAILED_CAPTION>"
        inputs = self.processor(text=task_prompt, images=image, return_tensors="pt").to(self.device)

        self.florence_model.to(self.device)

        with torch.no_grad():
            generated_ids = self.florence_model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3
            )

        self.florence_model.to('cpu')
        torch.cuda.empty_cache()

        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed_answer = self.processor.post_process_generation(generated_text, task=task_prompt, image_size=image.size)
        florence_description = parsed_answer[task_prompt]
        self.get_logger().info(f"👁️ 시각 센서 보고내용: {florence_description}")

        self.get_logger().info("📡 GPT-4o: 지휘관 AI에게 최종 판단 요청 중...")
        system_prompt = """
        당신은 군/경찰 특수부대 소속의 EOD(폭발물 처리) 로봇의 보안 분석 모듈입니다.
        시각 센서(Florence-2)로부터 전달받은 텍스트 묘사를 바탕으로 다음 '위험 지표'를 분석하십시오.

        [🚨 위험도 판별 기준 (매우 중요)]
        1. 안전: 일반적인 사무용품, 가구 등 폭발물과 전혀 무관한 일상적인 환경
        2. 확인 필요: 전선이나 배터리가 단독으로 굴러다니거나, 용도를 알 수 없는 수상한 상자가 있는 경우
        3. 위험 (사제 폭발물, IED): 플라스틱 병(페트병), 노출된 기판(보드), 배터리, 전선 등이 **테이프 등으로 조잡하게 얽혀 결합**되어 있다면 100% '위험'으로 판정할 것. 

        [보고 형식]
        - 추론 과정: 시각 정보에서 포착된 위험 징후들을 단계별로 나열
        - 종합 판단: (안전 / 확인 필요 / 위험) 중 하나 선택
        - 로봇 행동 지령: 구체적인 이동 및 센서 운용 명령
        """

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"시각 센서 보고: {florence_description}"}
            ]
        )

        final_decision = response.choices[0].message.content
        print("\n" + "="*50 + "\n🧠 중앙 통제 AI 명령서\n" + "-"*50)
        print(final_decision)
        print("="*50 + "\n")

        if "종합 판단: 안전" in final_decision or "종합 판단: (안전" in final_decision:
            self.get_logger().info("🟢 안전 판정! 타겟이 아닙니다. 탐색(순찰) 임무로 복귀합니다.")
            self.is_analyzing = False
            self.target_found = False 
            self.search_state = 0     
            self.last_move_time = time.time() - 20.0 
        else:
            self.get_logger().error("🔴 확인 필요 또는 위험 판정! 다음 3DGS 스캔 단계로 이행합니다.")
            save_dir = '/home/rokey/robot_share'
            os.makedirs(save_dir, exist_ok=True)
            image.save(os.path.join(save_dir, 'danger_object.jpg'))
            trigger_msg = Bool()
            trigger_msg.data = True
            self.scan_trigger_pub.publish(trigger_msg)

def main(args=None):
    rclpy.init(args=args)
    node = EODAnalyzerNode()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            if node.target_found and node.captured_image is not None:
                img_to_process = node.captured_image
                node.captured_image = None
                node.run_vlm_pipeline(img_to_process)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()