import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import os
import subprocess
import threading
from datetime import datetime
import shutil
import glob
import time
import json
import requests
import textwrap

# 클래스 생성 (경로에 맞게 확인해주세요)
from .utils.mesh_processor import PointCloudProcessor

class GSTrainerNode(Node):
    def __init__(self):
        super().__init__('gs_trainer_node')
        
        self.declare_parameter('robot_share_dir', '/root/robot_share')
        raw_path = self.get_parameter('robot_share_dir').value
        self.robot_share_dir = os.path.expanduser(raw_path)
        self.workspace = os.path.join(self.robot_share_dir, '3dgs_workspace')
        
        self.backend_url_save = "http://192.168.10.14:8080/api/ply/save"
        self.backend_url_upload_ply = "http://192.168.10.14:8080/api/ply/upload"
        self.backend_url_upload_json = "http://192.168.10.14:8080/api/ply/upload-grasp"
        
        self.json_publisher = self.create_publisher(String, '/voxel_json_result', 10)
        self.subscription = self.create_subscription(Bool, '/start_3dgs', self.trigger_callback, 10)
        self.is_training = False
        self.previous_intermediate_ply = None
        
        self.get_logger().info("🚀 Trainer Node started. Waiting for True on '/start_3dgs'...")

    def check_dataset_ready(self):
        if not os.path.exists(self.workspace):
            self.get_logger().error(f"❌ 데이터셋 경로를 찾을 수 없습니다: {self.workspace}")
            return False
        self.get_logger().info(f"✅ 공유 폴더 데이터셋 확인 완료! (경로: {self.workspace})")
        return True

    # ==========================================
    # 공통: 최신 config.yml 경로 찾기
    # ==========================================
    def get_latest_config(self):
        output_dir_path = os.path.join(self.robot_share_dir, '3dgs_outputs')
        search_pattern = os.path.join(output_dir_path, 'Feature_3DGS_Results', 'feature-splatfacto', '*', 'config.yml')
        config_files = glob.glob(search_pattern)
        if not config_files:
            return None
        return os.path.abspath(max(config_files, key=os.path.getctime))

    # ==========================================
    # ⚡ [새로 추가] 중간 추출용: 가볍고 빠른 PLY 추출 (Feature 제외)
    # ==========================================
    def export_fast_splat_to_ply(self, target_ply_path):
        abs_config_path = self.get_latest_config()
        if not abs_config_path: return None

        temp_dir = os.path.join(self.robot_share_dir, 'temp_fast_export')
        os.makedirs(temp_dir, exist_ok=True)

        # ns-export의 내장 기능을 사용해 순수 형태(XYZ, RGB)만 빠르게 추출
        command = [
            "ns-export", "gaussian-splat",
            "--load-config", abs_config_path,
            "--output-dir", temp_dir
        ]
        
        try:
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode == 0:
                default_ply = os.path.join(temp_dir, "splat.ply") # ns-export 기본 결과물
                if os.path.exists(default_ply):
                    shutil.move(default_ply, target_ply_path)
                    return target_ply_path
            return None
        except Exception as e:
            return None

    # ==========================================
    # 📦 최종 추출용: 무거운 PLY 추출 (Feature 포함, 기존 스크립트 사용)
    # ==========================================
    def export_full_splat_to_ply(self, target_ply_path):
        abs_config_path = self.get_latest_config()
        if not abs_config_path: return None
        
        script_code = textwrap.dedent(f"""
            import sys
            sys.path.append('/root/son_ws/3d_ws/src/3dgs_pkg/3dgs_pkg')
            import export_detect

            export_detect.CONFIG_PATH = '{abs_config_path}'
            export_detect.main()
        """)
        
        try:
            process = subprocess.run(["python3", "-c", script_code], capture_output=True, text=True)
            if process.returncode == 0:
                exported_plys = glob.glob(os.path.join(self.robot_share_dir, 'scan_*.ply'))
                if exported_plys:
                    latest_ply = max(exported_plys, key=os.path.getctime)
                    shutil.copy(latest_ply, target_ply_path)
                    return target_ply_path
            return None
        except Exception as e:
            return None

    def trigger_callback(self, msg):
        if not msg.data: return
        if self.is_training: return
        if not self.check_dataset_ready(): return

        self.is_training = True
        threading.Thread(target=self.run_3dgs_training, args=(self.workspace,)).start()

    def upload_to_backend(self, ply_path, json_path):
        ply_name = os.path.basename(ply_path) if ply_path else ""
        json_name = os.path.basename(json_path) if json_path else ""

        if ply_path and os.path.exists(ply_path):
            try:
                with open(ply_path, 'rb') as f:
                    requests.post(self.backend_url_upload_ply, files={'file': f}, timeout=10)
            except Exception: pass

        if json_path and os.path.exists(json_path):
            try:
                with open(json_path, 'rb') as f:
                    requests.post(self.backend_url_upload_json, files={'file': f}, timeout=10)
            except Exception: pass

        try:
            payload = {"file": ply_name, "graspDataFileName": json_name}
            requests.post(self.backend_url_save, json=payload, timeout=5)
        except Exception: pass

    # 실시간 확인용 중간 PLY를 뽑아서 백엔드로 전송
    def export_intermediate_ply(self):
        # 1. 프론트엔드가 무조건 "새 파일"로 인식하도록 매번 다른 이름(시간) 부여
        current_time = datetime.now().strftime("%H%M%S") # 시분초만 붙임
        temp_ply_path = os.path.join(self.robot_share_dir, f"scan_intermediate_{current_time}.ply")
        
        # 🚀 가벼운(Fast) 함수 호출!
        extracted_ply = self.export_fast_splat_to_ply(temp_ply_path)
        
        if extracted_ply:
            self.get_logger().info(f"🔄 실시간 확인용 중간 PLY 백엔드 전송 중... ({os.path.basename(extracted_ply)})")
            self.upload_to_backend(extracted_ply, None)
            
            # 2. 빗자루질: 하드디스크 용량 확보를 위해 '직전' 중간 파일은 조용히 삭제!
            if self.previous_intermediate_ply and os.path.exists(self.previous_intermediate_ply):
                try:
                    os.remove(self.previous_intermediate_ply)
                except Exception as e:
                    pass
            
            # 다음 턴을 위해 현재 파일을 '이전 파일'로 기억
            self.previous_intermediate_ply = extracted_ply

    def run_3dgs_training(self, dataset_path):
        self.get_logger().info("====================================")
        self.get_logger().info(f"[공유 폴더 직접 실행 모드] 3DGS 학습 시작!")
        self.get_logger().info("====================================")

        dataset_path_str = str(dataset_path) 
        transforms_path = os.path.join(dataset_path_str, 'transforms.json')
        ply_path = os.path.join(dataset_path_str, 'points3D.ply')

        if os.path.exists(ply_path) and os.path.exists(transforms_path):
            try:
                with open(transforms_path, 'r', encoding='utf-8') as f:
                    transforms_data = json.load(f)
                if transforms_data.get('ply_file_path') != 'points3D.ply':
                    transforms_data['ply_file_path'] = 'points3D.ply'
                    with open(transforms_path, 'w', encoding='utf-8') as f:
                        json.dump(transforms_data, f, indent=4)
            except Exception: pass

        output_dir_path = os.path.join(self.robot_share_dir, '3dgs_outputs')
        os.makedirs(output_dir_path, exist_ok=True)

        command = [
            "ns-train", "feature-splatfacto",
            "--experiment-name", "Feature_3DGS_Results",
            "--output-dir", output_dir_path,         
            "--pipeline.model.camera-optimizer.mode", "SO3xR3",
            "--vis", "tensorboard",
            "--pipeline.model.background-color", "black",
            "--pipeline.model.feature-loss-weight", "1.0",  
            "nerfstudio-data",
            f"--data={dataset_path_str}",        
            "--auto-scale-poses=False",          
            "--center-method=none",
            "--orientation-method=none",
            "--load-3D-points=True"              
        ]
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd=dataset_path)
            
            last_export_time = time.time()
            export_interval = 10.0  # 🌟 10초마다 중간 PLY 갱신

            for line in iter(process.stdout.readline, ''):
                if not line: break
                if rclpy.ok():
                    try:
                        self.get_logger().info(f"[ns-train] {line.strip()}")
                        
                        current_time = time.time()
                        if current_time - last_export_time >= export_interval:
                            last_export_time = current_time
                            # 🚀 백그라운드 스레드로 중간(빠른) PLY 추출 실행
                            threading.Thread(target=self.export_intermediate_ply, daemon=True).start()
                            
                    except Exception: pass
                else:
                    process.terminate()
                    break
                    
            process.wait()
            
            # 🔥 학습 완료 후 최종 PLY(Feature 포함) 추출 로직
            if process.returncode == 0 and rclpy.ok():
                self.get_logger().info("✅ 학습 완료! 최종 Feature 모델 및 파지점 처리를 시작합니다.")
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                time.sleep(5)
                
                exported_ply_path = os.path.join(self.robot_share_dir, f"exported_splat_{current_time}.ply")
                
                # 📦 최종 형태는 무거운 스크립트(export_detect.py)를 돌려서 Feature까지 추출!
                final_ply_path = self.export_full_splat_to_ply(exported_ply_path)
                
                json_filename = f"voxel_points_{current_time}.json"
                obj_filename = f"voxel_points_{current_time}.obj"  
                json_output_path = os.path.join(self.robot_share_dir, json_filename)
                obj_output_path = os.path.join(self.robot_share_dir, obj_filename) 
                
                process_target_ply = final_ply_path if final_ply_path else os.path.join(dataset_path, 'points3D.ply')
                
                processor = PointCloudProcessor(
                    ply_path=process_target_ply, 
                    output_json_path=json_output_path,
                    output_obj_path=obj_output_path
                )
                
                result_path = processor.process_all()
                
                if result_path and os.path.exists(result_path):
                    with open(result_path, 'r', encoding='utf-8') as f:
                        msg = String()
                        msg.data = f.read()
                    self.json_publisher.publish(msg)
                    self.get_logger().info("🚀 최종 변환 및 DB 전송 완료!")

                    # 최종 Feature PLY와 JSON을 백엔드로 전송
                    self.upload_to_backend(process_target_ply, result_path)
            elif not rclpy.ok():
                pass
            else:
                self.get_logger().error(f"❌ 학습 오류 (Code: {process.returncode})")
                
        except Exception as e:
            if rclpy.ok(): self.get_logger().error(f"❌ 서브프로세스 예외: {e}")
        finally:
            self.is_training = False

def main(args=None):
    rclpy.init(args=args)
    node = GSTrainerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()