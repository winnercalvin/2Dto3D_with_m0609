import rclpy
from rclpy.node import Node
import websocket, threading, json, os, time
import open3d as o3d

class PlyToObjNode(Node):
    def __init__(self):
        super().__init__('ply_to_obj_node')
        self.ws_url = "ws://192.168.10.14:8080/ws/robot"
        self.shared_dir = "/root/robot_share/"  
        self.alpha_size = 0.03
        
        threading.Thread(target=self.start_websocket, daemon=True).start()
        self.get_logger().info("🛠️ PLY->OBJ 변환 노드 시작 및 웹소켓 연결 시도 중...")

    def process_meshify(self, ply_filename):
        ply_path = os.path.join(self.shared_dir, ply_filename)
        obj_filename = ply_filename.replace('.ply', '.obj')
        output_obj_path = os.path.join(self.shared_dir, obj_filename)

        if not os.path.exists(ply_path):
            self.get_logger().error(f"❌ 파일을 찾을 수 없습니다: {ply_path}")
            return

        try:
            self.get_logger().info(f"📥 변환 시작: {ply_filename}")
            pcd = o3d.io.read_point_cloud(ply_path)
            pcd_clean, ind = pcd.remove_statistical_outlier(nb_neighbors=40, std_ratio=1.0)
            pcd_clean = pcd.select_by_index(ind)
            mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd_clean, self.alpha_size)
            mesh = mesh.filter_smooth_taubin(number_of_iterations=15)
            mesh.compute_vertex_normals()
            o3d.io.write_triangle_mesh(output_obj_path, mesh)
            self.get_logger().info(f"🎉 변환 완료 및 저장됨: {obj_filename}")
        except Exception as e:
            self.get_logger().error(f"⚠️ 변환 오류 발생: {e}")

    def start_websocket(self):
        def on_message(ws, message):
            # 모든 메시지 수신 로그 (디버깅용)
            # self.get_logger().info(f"📩 메시지 수신: {message}") 
            try:
                data = json.loads(message)
                if data.get("type") == "new_ply":
                    file_name = data.get("fileName")
                    self.get_logger().info(f"🔔 새 PLY 신호 감지: {file_name}")
                    self.process_meshify(file_name)
            except Exception as e:
                self.get_logger().error(f"⚠️ 메시지 처리 중 오류: {e}")

        def on_error(ws, error):
            self.get_logger().error(f"❌ 웹소켓 에러 발생: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.get_logger().warn(f"🔴 웹소켓 연결 종료 (코드: {close_status_code}, 메시지: {close_msg})")
            self.get_logger().info("🔄 3초 후 재연결을 시도합니다...")
            time.sleep(3)
            self.start_websocket()

        def on_open(ws):
            self.get_logger().info(f"🟢 웹소켓 서버 연결 성공! 주소: {self.ws_url}")

        # 웹소켓 객체 생성 및 실행
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        self.ws.run_forever()

def main(args=None):
    rclpy.init(args=args)
    node = PlyToObjNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("🛑 사용자에 의해 노드 종료")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()