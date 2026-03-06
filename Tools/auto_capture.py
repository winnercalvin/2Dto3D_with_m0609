import cv2
import os
import time
import re

# 1. 저장 경로 설정
save_path = '/home/sehoon/Tools/images'

if not os.path.exists(save_path):
    os.makedirs(save_path)
    print(f"폴더를 생성했습니다: {save_path}")

# --- 번호 자동 계산 로직 추가 ---
def get_next_count(path):
    files = [f for f in os.listdir(path) if f.startswith('capture_') and f.endswith('.jpg')]
    if not files:
        return 1
    
    # 파일명에서 숫자만 추출 (예: capture_139.jpg -> 139)
    numbers = []
    for f in files:
        nums = re.findall(r'\d+', f)
        if nums:
            numbers.append(int(nums[-1]))
            
    return max(numbers) + 1 if numbers else 1

# 시작 번호 자동 설정
count = get_next_count(save_path)
# ------------------------------

# 2. 카메라 설정 (C270: 4, 리얼센스: 0)
cam_id = 4 
cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)

if not cap.isOpened():
    print(f"오류: {cam_id}번 카메라를 열 수 없습니다.")
    exit()

interval = 5  # 5초 간격
last_capture_time = time.time()

print(f"저장 위치: {save_path}")
print(f"기존 파일을 확인했습니다. [ {count}번 ]부터 저장을 시작합니다.")
print("- 'q' 키: 수동 저장 / 'Esc' 키: 종료")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow('Camera Preview', frame)
    current_time = time.time()

    # 자동 캡처 (capture_번호.jpg)
    if current_time - last_capture_time >= interval:
        filename = os.path.join(save_path, f'capture_{count}.jpg')
        cv2.imwrite(filename, frame)
        print(f"[자동 저장] {filename}")
        
        count += 1
        last_capture_time = current_time 

    key = cv2.waitKey(1) & 0xFF

    # 수동 저장 (q 키)
    if key == ord('q'):
        filename = os.path.join(save_path, f'capture_{count}.jpg')
        cv2.imwrite(filename, frame)
        print(f"[수동 저장] {filename}")
        count += 1
    
    # 종료 (Esc 키)
    elif key == 27:
        print("프로그램을 종료합니다.")
        break

cap.release()
cv2.destroyAllWindows()