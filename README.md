# 💣 [2D to 3D 스캐닝 및 EOD(폭발물 처리) 로봇팔]
> **조 이름:** [프로젝트 팀 이름 입력]
> **팀원:** [팀원 이름 입력]

## 🎥 프로젝트 시연 영상 (Demo Video)

<p align="center">
  <a href="유튜브_링크_입력">
    <img src="https://img.youtube.com/vi/유튜브_영상_ID/0.jpg" width="700" alt="프로젝트 시연 영상">
  </a>
</p>

## 1. 🎨 시스템 설계 및 플로우 차트
프로젝트의 전체적인 구조와 소프트웨어 흐름도입니다. 

### 1-1. 시스템 설계도 (System Architecture)
![시스템 설계도](./images/system_design.png) ### 1-2. 플로우 차트 (Flow Chart)
```mermaid
graph TD
    %% 시작 및 음성 명령 단계
    Start([시작]) --> WhisperSTT[Whisper STT 음성 명령 수신]
    WhisperSTT --> StartScan[로봇팔 3Way 스캐닝 모션 시작]

    %% 2D to 3D 변환 단계
    StartScan --> CaptureImage[RealSense 카메라 데이터 수집]
    CaptureImage --> FeatureExtract[Feature 추출 및 3DGS 모델 학습]
    FeatureExtract --> PLYtoOBJ[PLY 3D 모델을 OBJ로 변환 및 최적화]
    
    %% 분석 및 조작 단계
    PLYtoOBJ --> YoloAnalysis[YOLOv11 기반 위험물/전선 분석]
    YoloAnalysis --> CheckDanger{폭발물/해체 대상인가?}
    
    CheckDanger -- "예 (타겟 확인)" --> MoveItPlanning[MoveIt 기반 매니퓰레이터 궤적 생성]
    CheckDanger -- "아니오 / 타겟 없음" --> Wait[대기 상태 전환]
    
    %% 로봇 팔 조작 및 완료
    MoveItPlanning --> GrabTarget[RG2 그리퍼로 목표물 파지 및 조작]
    GrabTarget --> End([작업 완료])
    Wait --> End

    %% 스타일링 적용
    style FeatureExtract fill:#fff4dd,stroke:#d4a017,stroke-width:2px
    style YoloAnalysis fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style CheckDanger fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style MoveItPlanning fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    
    %% 기본 스타일링
    style Start fill:#f9f,stroke:#333,stroke-width:2px
    style End fill:#f9f,stroke:#333,stroke-width:2px
