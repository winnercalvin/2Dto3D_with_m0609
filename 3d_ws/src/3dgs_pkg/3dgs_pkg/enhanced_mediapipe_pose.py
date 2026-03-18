# enhanced_mediapipe_pose.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
import sys
import time
import cv2
import mediapipe as mp
import numpy as np

sys.path.append('/home/rokey/cobot_ws/src/doosan-robot2/common2/imp')
sys.path.append('/home/rokey/cobot_ws/src/doosan-robot2/common2')
sys.path.append('/home/rokey/cobot_ws/src/doosan-robot2/dsr_common2/imp')

import DR_init

ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"

# 속도 증가
VELOCITY = 80   # VELOCITY = 120
ACC = 120       # ACC = 120

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL

# workspace 확대
"""
X_MIN, X_MAX = 300, 700
Y_MIN, Y_MAX = -350, 350
Z_MIN, Z_MAX = 100, 600
"""
X_MIN, X_MAX = 250, 750
Y_MIN, Y_MAX = -450, 450
Z_MIN, Z_MAX = 100, 650

MAX_STEP = 80   # singularity 방지

def clamp(v, mn, mx):
    return max(min(v, mx), mn)


# -----------------------------
# Robot Init
# -----------------------------

def initialize_robot():

    from DSR_ROBOT2 import set_robot_mode, ROBOT_MODE_AUTONOMOUS, movej

    set_robot_mode(ROBOT_MODE_AUTONOMOUS)

    movej([0,0,90,0,90,0], vel=60, acc=60)

    print("Robot Ready")


# -----------------------------
# Fist detection
# -----------------------------

def is_fist(hand_landmarks):

    tip = hand_landmarks.landmark[8]
    pip = hand_landmarks.landmark[6]

    return tip.y > pip.y


# -----------------------------
# Main Teleoperation
# -----------------------------

def robot_follow():

    from DSR_ROBOT2 import movel, amovel, get_current_posx

    mp_pose = mp.solutions.pose
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    pose = mp_pose.Pose(model_complexity=0)

    hands = mp_hands.Hands(
        model_complexity=0,
        max_num_hands=1)

    cap = cv2.VideoCapture(0)

    # cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    # 해상도 확대
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)

    # 버퍼 제거 (freeze 해결)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)

    smooth=None
    last_move=0
    last_grip=False

    print("Camera Start")

    while cap.isOpened():

        ret,frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame,1)

        h,w,_ = frame.shape

        rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

        pose_res = pose.process(rgb)
        hand_res = hands.process(rgb)

        # -----------------------------
        # ARM VISUALIZATION
        # -----------------------------

        if pose_res.pose_landmarks:

            lm = pose_res.pose_landmarks.landmark

            s = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
            e = lm[mp_pose.PoseLandmark.RIGHT_ELBOW]
            wri = lm[mp_pose.PoseLandmark.RIGHT_WRIST]

            sx,sy=int(s.x*w),int(s.y*h)
            ex,ey=int(e.x*w),int(e.y*h)
            wx,wy=int(wri.x*w),int(wri.y*h)

            cv2.line(frame,(sx,sy),(ex,ey),(255,0,0),3)
            cv2.line(frame,(ex,ey),(wx,wy),(255,0,0),3)

        # -----------------------------
        # HAND TRACKING
        # -----------------------------

        if hand_res.multi_hand_landmarks:

            for hand in hand_res.multi_hand_landmarks:

                mp_draw.draw_landmarks(
                    frame,hand,mp_hands.HAND_CONNECTIONS)

                xs=[int(l.x*w) for l in hand.landmark]
                ys=[int(l.y*h) for l in hand.landmark]

                min_x,max_x=min(xs),max(xs)
                min_y,max_y=min(ys),max(ys)

                box=(max_x-min_x)*(max_y-min_y)

                if box==0:
                    continue

                # Z scaling 증가
                pseudo_z = 40000/box

                tip=hand.landmark[
                    mp_hands.HandLandmark.INDEX_FINGER_TIP]

                x=int(tip.x*w)
                y=int(tip.y*h)

                cv2.rectangle(frame,(min_x,min_y),(max_x,max_y),(0,255,0),2)

                cv2.putText(frame,
                    f"X:{x} Y:{y} Z:{pseudo_z:.1f}",
                    (30,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,(0,0,255),2)

                # -----------------------------
                # ROBOT CONTROL
                # -----------------------------

                if time.time()-last_move>0.05:

                    pos = get_current_posx()[0]

                    x_r = pos[0] + pseudo_z*0.25
                    y_r = pos[1] + (x-320)*0.7
                    z_r = pos[2] + (240-y)*0.7

                    x_r=clamp(x_r,X_MIN,X_MAX)
                    y_r=clamp(y_r,Y_MIN,Y_MAX)
                    z_r=clamp(z_r,Z_MIN,Z_MAX)

                    target=[x_r,y_r,z_r]+pos[3:]
                    
                    
                    """
                    # singularity 방지 (step 제한)
                    dist=np.linalg.norm(
                        np.array(target[:3])-
                        np.array(pos[:3]))

                    if dist>MAX_STEP:
                        print("Singularity risk → motion skipped")
                        continue
                    """
                    # smoothing
                    if smooth is None:
                        smooth=target
                    else:
                        alpha=0.4
                        smooth=[
                            alpha*t+(1-alpha)*s
                            for t,s in zip(target,smooth)
                        ]
                    """
                    movel(
                        smooth,
                        vel=VELOCITY,
                        acc=ACC,
                        async_=True
                    )
                    """
                    amovel(
                        smooth,
                        vel=VELOCITY,
                        acc=ACC
                    )

                    last_move=time.time()

                # -----------------------------
                # GRIPPER CONTROL
                # -----------------------------

                fist=is_fist(hand)

                if fist and not last_grip:

                    print("GRIP CLOSE")
                    last_grip=True

                elif not fist and last_grip:

                    print("GRIP OPEN")
                    last_grip=False

        cv2.imshow("Robot Teleoperation",frame)

        if cv2.waitKey(1)==27:
            break

    cap.release()
    cv2.destroyAllWindows()


# -----------------------------
# MAIN
# -----------------------------

def main():

    rclpy.init()

    node=rclpy.create_node(
        "hand_follow_node",
        namespace=ROBOT_ID)

    DR_init.__dsr__node=node

    try:

        initialize_robot()

        robot_follow()

    except KeyboardInterrupt:
        pass

    finally:

        rclpy.shutdown()


if __name__=="__main__":
    main()
