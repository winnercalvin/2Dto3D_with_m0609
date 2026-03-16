import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray, String
import websocket, threading, json, time

class RobotPoseNode(Node):
    def __init__(self):
        super().__init__('robot_pose_node')
        
        # 🔥 로봇 팔에 직접 좌표를 쏘는 퍼블리셔 (x, y, z, rx, ry, rz)
        self.cmd_publisher = self.create_publisher(Float64MultiArray, '/target_point', 10)
        
        # 아까 만든 Whisper STT 노드의 말을 엿듣는 구독자
        self.stt_subscription = self.create_subscription(String, '/robot_stt_command', self.stt_callback, 10)

        self.ws_url = "ws://192.168.10.14:8080/ws/robot"

        self.get_logger().info("✅ 음성 명령 다이렉트 좌표 전송 노드 준비 완료!")
        threading.Thread(target=self.start_websocket, daemon=True).start()

    def stt_callback(self, msg):
        """STT에서 문장이 들어오면 색상을 파악하고 즉시 좌표를 쏩니다."""
        text = msg.data
        self.get_logger().info(f"🗣️ 들은 문장: '{text}'")
        
        if "빨간" in text or "빨강" in text or "red" in text.lower():
            self.get_logger().info("🎯 '빨간색' 인식됨! 빨간 선 좌표를 즉시 전송합니다.")
            self.send_target_coordinates("red wire")
            
        elif "파란" in text or "파랑" in text or "blue" in text.lower():
            self.get_logger().info("🎯 '파란색' 인식됨! 파란 선 좌표를 즉시 전송합니다.")
            self.send_target_coordinates("blue wire")
            
        else:
            self.get_logger().info("🤔 문장에서 타겟 색상을 찾을 수 없습니다.")

    def send_target_coordinates(self, target_name):
        """타겟에 맞는 좌표를 생성하여 로봇으로 전송합니다."""
        
        # 💡 테스트용 임시 좌표입니다. 나중에 3DGS에서 계산된 실제 좌표 변수로 교체하세요!
        if target_name == "red wire":
            # 빨간 선의 x, y, z, rx, ry, rz 좌표 (임시)
            target_pose = [0.45, 0.12, 0.30, 3.14, 0.0, 0.0] 
        elif target_name == "blue wire":
            # 파란 선의 x, y, z, rx, ry, rz 좌표 (임시)
            target_pose = [0.45, -0.15, 0.30, 3.14, 0.0, 0.0]
        else:
            return

        # 배열(Float64MultiArray)에 담아서 퍼블리시
        msg = Float64MultiArray()
        msg.data = target_pose
        self.cmd_publisher.publish(msg)
        
        self.get_logger().info(f"🚀 로봇 팔로 좌표 다이렉트 전송 완료: {target_pose}")

    def start_websocket(self):
        def on_open(ws):
            self.get_logger().info(f"🔗 웹소켓 서버({self.ws_url})에 연결 성공!")

        def on_error(ws, error):
            self.get_logger().error(f"❌ 웹소켓 에러: {error}")

        def on_message(ws, message):
            self.get_logger().info(f"📥 웹소켓 데이터 도착: {message}")
            try:
                data = json.loads(message)
                
                # 웹소켓으로 텍스트 명령이 들어왔을 때도 STT와 똑같이 처리
                if data.get("type") == "text_command" or "text" in data:
                    text_msg = String()
                    text_msg.data = data.get("text", "")
                    self.stt_callback(text_msg)

                # 웹소켓으로 수동 좌표가 들어왔을 때
                elif data.get("type") == "pose_command" or "x" in data:
                    x = float(data.get("x", 0.0))
                    y = float(data.get("y", 0.0))
                    z = float(data.get("z", 0.0))
                    rx = float(data.get("rx", 0.0))
                    ry = float(data.get("ry", 0.0))
                    rz = float(data.get("rz", 0.0))

                    msg = Float64MultiArray()
                    msg.data = [x, y, z, rx, ry, rz]
                    
                    self.cmd_publisher.publish(msg)
                    self.get_logger().info(f"🚀 수동 목표 좌표 전송 완료: {list(msg.data)}")
                
            except ValueError:
                self.get_logger().error("⚠️ 좌표값은 숫자여야 합니다.")
            except Exception as e:
                self.get_logger().error(f"메시지 처리 오류: {e}")

        def on_close(ws, close_status_code, close_msg):
            self.get_logger().warn("⚠️ 웹소켓 연결 끊김. 3초 후 재연결...")
            time.sleep(3)
            self.start_websocket()

        self.ws = websocket.WebSocketApp(
            self.ws_url, on_open=on_open, on_message=on_message, 
            on_error=on_error, on_close=on_close
        )
        self.ws.run_forever()

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(RobotPoseNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()