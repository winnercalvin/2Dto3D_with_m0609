import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os
import json
import subprocess
import threading
from datetime import datetime

# 클래스 생성
from .utils.mesh_processor import PointCloudProcessor

class GSTrainerNode(Node):
    def __init__(self):
        super().__init__('gs_trainer_node')
        
        # 파라미터 설정 (기본 최상위 작업 폴더)
        self.declare_parameter('robot_share_dir', '/home/rokey/robot_share')
        self.robot_share_dir = self.get_parameter('robot_share_dir').value
        
        # JSON 변환 결과를 발행할 Publisher
        self.json_publisher = self.create_publisher(
            String, 
            '/voxel_json_result', 
            10
        )
        
        # 학습 시작 트리거 토픽 구독 (이제 msg.data로 '폴더명'이 들어옵니다)
        self.subscription = self.create_subscription(
            String,
            '/start_3dgs',
            self.trigger_callback,
            10
        )
        
        self.is_training = False
        self.get_logger().info("🚀 Nerfstudio Trainer Node started. Waiting for folder name on '/start_3dgs'...")

    def trigger_callback(self, msg):
        if self.is_training:
            self.get_logger().warn("⚠️ 이미 학습이 진행 중입니다. 요청을 무시합니다.")
            return
            
        # 🌟 1. 토픽으로 들어온 폴더명 수신 및 경로 병합
        folder_name = msg.data.strip()
        target_dataset_path = os.path.join(self.robot_share_dir, folder_name)
        
        self.get_logger().info(f"📥 트리거 수신됨 (대상 폴더): {folder_name}")
        self.get_logger().info(f"🔍 데이터 검증 경로: {target_dataset_path}")
        
        # 해당 폴더 안에 transforms.json이 있는지 검증
        transform_path = os.path.join(target_dataset_path, 'transforms.json')
        if not os.path.exists(transform_path):
            self.get_logger().error(f"❌ 오류: {transform_path} 파일을 찾을 수 없습니다. 폴더명을 확인하세요.")
            return
            
        self.is_training = True
        
        # 🌟 2. 스레드에 타겟 데이터셋 경로(target_dataset_path)를 인자로 넘겨줍니다.
        training_thread = threading.Thread(target=self.run_3dgs_training, args=(target_dataset_path,))
        training_thread.start()

    def run_3dgs_training(self, dataset_path):
        self.get_logger().info("====================================")
        self.get_logger().info(f"   [{os.path.basename(dataset_path)}] 3DGS 학습을 시작합니다!   ")
        self.get_logger().info("====================================")
        
        # 🌟 3. 명령어의 --data 경로를 동적으로 받은 dataset_path로 변경
        command = [
            "ns-train", "splatfacto",
            "--experiment-name", f"robot_taco_{os.path.basename(dataset_path)}", # 실험 이름도 폴더명에 맞춤
            "--pipeline.model.camera-optimizer.mode", "off",
            "--vis", "tensorboard",
            "--pipeline.model.background-color", "black",
            "nerfstudio-data",
            "--data", dataset_path,
            "--auto-scale-poses", "False",
            "--center-method", "none",
            "--orientation-method", "none",
            "--load-3D-points", "True"
        ]
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 실시간 로그 출력
            for line in process.stdout:
                self.get_logger().info(f"[ns-train] {line.strip()}")
                
            process.wait()
            
            if process.returncode == 0:
                self.get_logger().info("✅ 학습이 성공적으로 완료되었습니다! 포인트 클라우드 처리를 시작합니다.")
                
                # 🌟 4. 현재 시간으로 JSON 파일명 동적 생성 (예: voxel_points_20260312_143000.json)
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_filename = f"voxel_points_{current_time}.json"
                json_output_path = os.path.join(self.robot_share_dir, json_filename)
                
                # 🌟 5. input.ply 파일 위치 지정 (해당 데이터셋 폴더 안에 있다고 가정)
                # 만약 항상 /home/rokey/robot_share/input.ply 고정이라면 기존 코드로 되돌리시면 됩니다.
                ply_path = os.path.join(dataset_path, 'input.ply')
                
                if not os.path.exists(ply_path):
                    self.get_logger().warn(f"⚠️ 경고: {ply_path} 가 존재하지 않습니다! Processor에서 에러가 날 수 있습니다.")
                
                processor = PointCloudProcessor(
                    ply_path=ply_path,
                    output_json_path=json_output_path
                )
                
                # 결과 파일 경로 반환받기
                result_path = processor.process_all()
                
                # JSON 처리가 완료되었다면 파일을 읽어 토픽으로 퍼블리시
                if result_path and os.path.exists(result_path):
                    with open(result_path, 'r', encoding='utf-8') as f:
                        json_string = f.read()
                        
                    msg = String()
                    msg.data = json_string
                    self.json_publisher.publish(msg)
                    
                    self.get_logger().info(f"🚀 변환 완료! 파일 저장 위치: {result_path}")
                    self.get_logger().info("📡 JSON 데이터를 '/voxel_json_result' 토픽으로 성공적으로 발행했습니다!")
                else:
                    self.get_logger().error("❌ 포인트 클라우드 처리 실패 또는 JSON 파일을 찾을 수 없습니다.")
                    
            else:
                self.get_logger().error(f"❌ 학습 중 오류가 발생했습니다. (Return Code: {process.returncode})")
                
        except Exception as e:
            self.get_logger().error(f"❌ 서브프로세스 실행 중 예외 발생: {e}")
            
        finally:
            self.is_training = False

def main(args=None):
    rclpy.init(args=args)
    node = GSTrainerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard Interrupt (SIGINT)')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()