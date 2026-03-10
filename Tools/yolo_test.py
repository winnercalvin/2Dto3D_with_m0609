import cv2
from ultralytics import YOLO

# 1. 학습한 모델 불러오기 (경로를 본인의 best.pt 위치로 수정하세요)
model_path = '/home/sehoon/0309/yolov11n_add/best.pt' 
model = YOLO(model_path)

# 2. 카메라 설정 
cam_id = 4
cap = cv2.VideoCapture(cam_id)

if not cap.isOpened():
    print(f"카메라 {cam_id}번을 열 수 없습니다.")
    exit()

print("실시간 탐지를 시작합니다. 종료하려면 'q'를 누르세요.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 3. 모델로 예측 수행 (conf 인자로 최소 확률 설정 가능)
    # stream=True는 메모리 효율을 위해 사용합니다.
    results = model(frame, stream=True, conf=0.5) # 25% 확률 이상만 표시

    for r in results:
        # 화면에 박스와 컨피던스(conf)를 그려준 이미지를 가져옴
        annotated_frame = r.plot() 
        
        # 터미널에도 실시간으로 확률 출력하고 싶다면 아래 주석 해제
        # for box in r.boxes:
        #     print(f"Detected: {model.names[int(box.cls)]} | Conf: {box.conf[0]:.2f}")

    # 4. 화면 표시
    cv2.imshow("YOLO Real-time Check", annotated_frame)

    # 'q' 누르면 종료
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
