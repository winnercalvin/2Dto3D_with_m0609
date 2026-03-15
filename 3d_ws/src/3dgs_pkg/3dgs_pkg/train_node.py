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

# 클래스 생성 (경로에 맞게 확인해주세요)
from .utils.mesh_processor import PointCloudProcessor

class GSTrainerNode(Node):
    def __init__(self):
        super().__init__('gs_trainer_node')
        
        self.declare_parameter('robot_share_dir', '~/robot_share')
        raw_path = self.get_parameter('robot_share_dir').value
        self.robot_share_dir = os.path.expanduser(raw_path)
        
        # 🌟 원본 데이터셋 (공유 폴더)
        self.source_workspace = os.path.join(self.robot_share_dir, '3dgs_workspace')
        
        # 🌟 로컬 작업 공간 (SSD 환경)
        self.local_workspace = '/root/son_ws/3dgs_workspace'
        
        self.json_publisher = self.create_publisher(String, '/voxel_json_result', 10)
        self.subscription = self.create_subscription(Bool, '/start_3dgs', self.trigger_callback, 10)
        self.is_training = False
        
        self.get_logger().info("🚀 Trainer Node started. Waiting for True on '/start_3dgs'...")

    def prepare_local_dataset(self):
        """공유 폴더의 세팅 완료된 데이터셋을 로컬 환경으로 복사합니다. (features 폴더 제외)"""
        if not os.path.exists(self.source_workspace):
            self.get_logger().error(f"❌ 원본 데이터셋이 없습니다: {self.source_workspace}")
            return False

        try:
            if os.path.exists(self.local_workspace):
                shutil.rmtree(self.local_workspace)
            
            self.get_logger().info("📥 공유 폴더의 데이터셋을 로컬 SSD로 캐싱 중입니다... ('features' 폴더 제외)")
            
            shutil.copytree(
                self.source_workspace, 
                self.local_workspace,
                ignore=shutil.ignore_patterns('features')
            )
            
            # 👇 --- 추가된 부분: images 폴더 안의 파일들을 최상단으로 빼기 --- 👇
            images_dir = os.path.join(self.local_workspace, 'images')
            if os.path.exists(images_dir):
                self.get_logger().info("📂 'images' 폴더 내의 이미지들을 작업 공간 최상단으로 이동합니다...")
                
                for filename in os.listdir(images_dir):
                    src_file = os.path.join(images_dir, filename)
                    dst_file = os.path.join(self.local_workspace, filename)
                    
                    # 파일만 이동 (혹시 폴더가 있다면 무시)
                    if os.path.isfile(src_file):
                        shutil.move(src_file, dst_file)
                
                # 파일 이동이 끝난 후 빈 images 폴더 삭제 (안전을 위해 빈 폴더일 때만 삭제됨)
                try:
                    os.rmdir(images_dir)
                    self.get_logger().info("✅ 이미지 이동 완료 및 빈 images 폴더 삭제됨.")
                except OSError:
                    self.get_logger().warn("⚠️ images 폴더에 이동할 수 없는 다른 디렉토리가 남아 있어 폴더를 삭제하지 않았습니다.")

            json_path = os.path.join(self.local_workspace, 'transforms.json')
            if os.path.exists(json_path):
                self.get_logger().info("📝 transforms.json 내부의 'images/' 경로를 수정하고 ply_file_path를 추가합니다...")
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    data['ply_file_path'] = "points3D.ply"

                    # frames 리스트를 돌면서 file_path에서 'images/' 제거
                    if 'frames' in data:
                        for frame in data['frames']:
                            file_path = frame.get('file_path', '')
                            if file_path.startswith('images/'):
                                # 'images/'를 ''(빈 문자열)로 교체
                                frame['file_path'] = file_path.replace('images/', '', 1)
                                
                    # 수정된 데이터를 다시 저장
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                        
                    self.get_logger().info("✅ transforms.json 수정 및 ply_file_path 추가 완료!")
                except Exception as e:
                    self.get_logger().error(f"❌ transforms.json 수정 중 오류 발생: {e}")
            else:
                self.get_logger().warn("⚠️ transforms.json 파일을 찾을 수 없습니다.")

            self.get_logger().info(f"✅ 로컬 데이터 준비 완료! (경로: {self.local_workspace})")
            return True
            
        except Exception as e:
            self.get_logger().error(f"❌ 데이터 복사 중 오류 발생: {e}")
            return False

    def export_splat_to_ply(self, workspace_dir, target_ply_path):
        search_pattern = os.path.join(workspace_dir, 'outputs', '*', 'splatfacto', '*', 'config.yml')
        config_files = glob.glob(search_pattern)
        
        if not config_files:
            return None
            
        latest_config = max(config_files, key=os.path.getctime)
        abs_config_path = os.path.abspath(latest_config)
        
        self.get_logger().info(f"🔍 절대 경로 확인: {abs_config_path}")
        
        export_dir = os.path.join(workspace_dir, 'export_temp')
        os.makedirs(export_dir, exist_ok=True)
        
        command = [
            "ns-export", "gaussian-splat",
            "--load-config", abs_config_path, 
            "--output-dir", "export_temp"     
        ]
        
        try:
            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                cwd=workspace_dir 
            )
            
            if process.returncode == 0:
                exported_plys = glob.glob(os.path.join(export_dir, '*.ply'))
                if exported_plys:
                    shutil.copy(exported_plys[0], target_ply_path)
                    self.get_logger().info(f"✅ PLY 추출 및 공유 폴더 저장 성공: {target_ply_path}")
                    return target_ply_path
            else:
                self.get_logger().error(f"❌ ns-export 에러 (Code {process.returncode})")
                self.get_logger().error(f"상세내용: {process.stderr}")
                return None
        except Exception as e:
            self.get_logger().error(f"❌ 실행 중 예외: {e}")
            return None

    def trigger_callback(self, msg):
        if not msg.data:
            self.get_logger().info("📩 False 수신. 대기 모드 유지.")
            return

        if self.is_training:
            self.get_logger().warn("⚠️ 이미 학습이 진행 중입니다.")
            return
            
        if not self.prepare_local_dataset():
            return

        self.is_training = True
        training_thread = threading.Thread(target=self.run_3dgs_training, args=(self.local_workspace,))
        training_thread.start()

    def run_3dgs_training(self, dataset_path):
        self.get_logger().info("====================================")
        self.get_logger().info(f"[로컬 SSD 모드] 3DGS 학습 시작!")
        self.get_logger().info("====================================")
        
        command = [
            "ns-train", "splatfacto",
            "--experiment-name", "BiRefNet_Results",
            "--pipeline.model.camera-optimizer.mode", "off",
            "--vis", "viewer",
            #"--viewer.websocket-ip", "0.0.0.0",           # 🌟 도커 외부 접속 허용 (Viser 서버)
            "--viewer.websocket-port", "7007",            # 🌟 포트 지정
            "--viewer.quit-on-train-completion", "True",  # 🌟 무한 대기 방지! 학습 끝나면 자동 종료
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
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                cwd=dataset_path 
            )
            
            # 🌟 Destroyable 에러 방지용: rclpy.ok() 체크 및 안전한 로그 읽기
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                if rclpy.ok():
                    try:
                        self.get_logger().info(f"[ns-train] {line.strip()}")
                    except Exception:
                        pass # ROS 노드가 셧다운 중일 때 발생하는 에러 무시
                else:
                    # 사용자가 Ctrl+C로 노드를 강제 종료하면 서브프로세스도 함께 킬
                    process.terminate()
                    break
                    
            process.wait()
            
            # rclpy가 살아있고, 학습이 정상(0)으로 끝났을 때만 다음 단계 진행
            if process.returncode == 0 and rclpy.ok():
                self.get_logger().info("✅ 학습 성공! 내장 기능으로 PLY 추출을 진행합니다.")
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                time.sleep(5)
                
                exported_ply_path = os.path.join(self.robot_share_dir, f"exported_splat_{current_time}.ply")
                final_ply_path = self.export_splat_to_ply(dataset_path, exported_ply_path)
                
                json_filename = f"voxel_points_{current_time}.json"
                obj_filename = f"voxel_points_{current_time}.obj"  
                
                json_output_path = os.path.join(self.robot_share_dir, json_filename)
                obj_output_path = os.path.join(self.robot_share_dir, obj_filename) 
                
                process_target_ply = final_ply_path if final_ply_path else os.path.join(dataset_path, 'point3D.ply')
                
                processor = PointCloudProcessor(
                    ply_path=process_target_ply, 
                    output_json_path=json_output_path,
                    output_obj_path=obj_output_path
                )
                
                result_path = processor.process_all()
                
                if result_path and os.path.exists(result_path):
                    with open(result_path, 'r', encoding='utf-8') as f:
                        json_string = f.read()
                    msg = String()
                    msg.data = json_string
                    self.json_publisher.publish(msg)
                    self.get_logger().info("🚀 변환 및 토픽 발행 완료! (JSON과 OBJ 파일이 공유 폴더에 저장되었습니다)")
                else:
                    self.get_logger().error("❌ JSON 파일 생성 실패.")
            elif not rclpy.ok():
                pass # 강제 종료 시 조용히 넘김
            else:
                self.get_logger().error(f"❌ 학습 오류 (Code: {process.returncode})")
                
        except Exception as e:
            if rclpy.ok():
                self.get_logger().error(f"❌ 서브프로세스 예외: {e}")
        finally:
            self.is_training = False

def main(args=None):
    rclpy.init(args=args)
    node = GSTrainerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard Interrupt')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()