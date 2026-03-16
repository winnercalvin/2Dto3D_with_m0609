import { WebPCodec } from '@playcanvas/splat-transform';
import { Color, createGraphicsDevice } from 'playcanvas';

import { registerCameraPosesEvents } from './camera-poses';
import { registerDocEvents } from './doc';
import { EditHistory } from './edit-history';
import { registerEditorEvents } from './editor';
import { Events } from './events';
import { initFileHandler } from './file-handler';
import { registerIframeApi } from './iframe-api';
import { registerPlySequenceEvents } from './ply-sequence';
import { registerPublishEvents } from './publish';
import { registerRenderEvents } from './render';
import { Scene } from './scene';
import { getSceneConfig } from './scene-config';
import { registerSelectionEvents } from './selection';
import { ShortcutManager } from './shortcut-manager';
import { registerTimelineEvents } from './timeline';
import { BoxSelection } from './tools/box-selection';
import { BrushSelection } from './tools/brush-selection';
import { EyedropperSelection } from './tools/eyedropper-selection';
import { FloodSelection } from './tools/flood-selection';
import { LassoSelection } from './tools/lasso-selection';
import { MeasureTool } from './tools/measure-tool';
import { MoveTool } from './tools/move-tool';
import { PolygonSelection } from './tools/polygon-selection';
import { RectSelection } from './tools/rect-selection';
import { RotateTool } from './tools/rotate-tool';
import { ScaleTool } from './tools/scale-tool';
import { SphereSelection } from './tools/sphere-selection';
import { ToolManager } from './tools/tool-manager';
import { registerTrackManagerEvents } from './track-manager';
import { registerTransformHandlerEvents } from './transform-handler';
import { EditorUI } from './ui/editor';
import { localizeInit } from './ui/localization';

declare global {
    interface LaunchParams {
        readonly files: FileSystemFileHandle[];
    }

    interface Window {
        launchQueue: {
            setConsumer: (callback: (launchParams: LaunchParams) => void) => void;
        };
        scene: Scene;
    }
}

const getURLArgs = () => {
    const config = {};
    const apply = (key: string, value: string) => {
        let obj: any = config;
        key.split('.').forEach((k, i, a) => {
            if (i === a.length - 1) {
                obj[k] = value;
            } else {
                if (!obj.hasOwnProperty(k)) {
                    obj[k] = {};
                }
                obj = obj[k];
            }
        });
    };
    const params = new URLSearchParams(window.location.search.slice(1));
    params.forEach((value: string, key: string) => {
        apply(key, value);
    });
    return config;
};

const main = async () => {
    const events = new Events();
    const url = new URL(window.location.href);
    const editHistory = new EditHistory(events);

    await localizeInit();

    WebPCodec.wasmUrl = new URL('static/lib/webp/webp.wasm', document.baseURI).toString();

    registerTimelineEvents(events);
    registerCameraPosesEvents(events);
    registerTrackManagerEvents(events);
    registerTransformHandlerEvents(events);
    registerPlySequenceEvents(events);
    registerPublishEvents(events);
    registerIframeApi(events);

    const shortcutManager = new ShortcutManager(events);
    events.function('shortcutManager', () => shortcutManager);

    const editorUI = new EditorUI(events);

    const graphicsDevice = await createGraphicsDevice(editorUI.canvas, {
        deviceTypes: ['webgl2'],
        antialias: false,
        depth: false,
        stencil: false,
        xrCompatible: false,
        powerPreference: 'high-performance'
    });

    const overrides = [getURLArgs()];
    const sceneConfig = getSceneConfig(overrides);

    const scene = new Scene(
        events,
        sceneConfig,
        editorUI.canvas,
        graphicsDevice
    );

    const bgClr = new Color();
    const selectedClr = new Color();
    const unselectedClr = new Color();
    const lockedClr = new Color();

    const setClr = (target: Color, value: Color, event: string) => {
        if (!target.equals(value)) {
            target.copy(value);
            events.fire(event, target);
        }
    };

    const setBgClr = (clr: Color) => setClr(bgClr, clr, 'bgClr');
    const setSelectedClr = (clr: Color) => setClr(selectedClr, clr, 'selectedClr');
    const setUnselectedClr = (clr: Color) => setClr(unselectedClr, clr, 'unselectedClr');
    const setLockedClr = (clr: Color) => setClr(lockedClr, clr, 'lockedClr');

    events.on('setBgClr', (clr: Color) => setBgClr(clr));
    events.on('setSelectedClr', (clr: Color) => setSelectedClr(clr));
    events.on('setUnselectedClr', (clr: Color) => setUnselectedClr(clr));
    events.on('setLockedClr', (clr: Color) => setLockedClr(clr));

    events.function('bgClr', () => bgClr);
    events.function('selectedClr', () => selectedClr);
    events.function('unselectedClr', () => unselectedClr);
    events.function('lockedClr', () => lockedClr);

    events.on('bgClr', (clr: Color) => {
        const cnv = (v: number) => `${Math.max(0, Math.min(255, (v * 255))).toFixed(0)}`;
        document.body.style.backgroundColor = `rgba(${cnv(clr.r)},${cnv(clr.g)},${cnv(clr.b)},1)`;
    });
    events.on('selectedClr', () => { scene.forceRender = true; });
    events.on('unselectedClr', () => { scene.forceRender = true; });
    events.on('lockedClr', () => { scene.forceRender = true; });

    const toColor = (value: { r: number, g: number, b: number, a: number }) => new Color(value.r, value.g, value.b, value.a);
    setBgClr(toColor(sceneConfig.bgClr));
    setSelectedClr(toColor(sceneConfig.selectedClr));
    setUnselectedClr(toColor(sceneConfig.unselectedClr));
    setLockedClr(toColor(sceneConfig.lockedClr));

    const maskCanvas = document.createElement('canvas');
    const maskContext = maskCanvas.getContext('2d');
    maskCanvas.setAttribute('id', 'mask-canvas');
    maskContext.globalCompositeOperation = 'copy';
    const mask = { canvas: maskCanvas, context: maskContext };

    const toolManager = new ToolManager(events);
    toolManager.register('rectSelection', new RectSelection(events, editorUI.toolsContainer.dom));
    toolManager.register('brushSelection', new BrushSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register('floodSelection', new FloodSelection(events, editorUI.toolsContainer.dom, mask, editorUI.canvasContainer));
    toolManager.register('polygonSelection', new PolygonSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register('lassoSelection', new LassoSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register('sphereSelection', new SphereSelection(events, scene, editorUI.canvasContainer));
    toolManager.register('boxSelection', new BoxSelection(events, scene, editorUI.canvasContainer));
    toolManager.register('eyedropperSelection', new EyedropperSelection(events, editorUI.toolsContainer.dom, editorUI.canvasContainer));
    toolManager.register('move', new MoveTool(events, scene));
    toolManager.register('rotate', new RotateTool(events, scene));
    toolManager.register('scale', new ScaleTool(events, scene));
    toolManager.register('measure', new MeasureTool(events, scene, editorUI.toolsContainer.dom, editorUI.canvasContainer));

    editorUI.toolsContainer.dom.appendChild(maskCanvas);

    window.scene = scene;

    registerEditorEvents(events, editHistory, scene);
    registerSelectionEvents(events, scene);
    registerDocEvents(scene, events);
    registerRenderEvents(scene, events);
    initFileHandler(scene, events, editorUI.appContainer.dom);

    scene.start();

    const loadList = url.searchParams.getAll('load');
    const filenameList = url.searchParams.getAll('filename');
    for (const [i, value] of loadList.entries()) {
        const decoded = decodeURIComponent(value);
        const filename = i < filenameList.length ? decodeURIComponent(filenameList[i]) : decoded.split('/').pop();
        await events.invoke('import', [{ filename, url: decoded }]);
    }

    if ('launchQueue' in window) {
        window.launchQueue.setConsumer(async (launchParams: LaunchParams) => {
            for (const file of launchParams.files) {
                await events.invoke('import', [{ filename: file.name, contents: await file.getFile() }]);
            }
        });
    }

    // =========================================================
    // 🚀 [커스텀 로직] 데이터베이스 연동, 다각형 선택, 그리고 STT (음성 인식)
    // =========================================================
    setTimeout(async () => {
        try {
            console.log("🛠️ 커스텀 UI 및 STT 세팅 시작...");

            const baseCamera = scene.camera.camera;
            const pcCamera = (baseCamera as any).camera || baseCamera;
            if (pcCamera) {
                pcCamera.nearClip = 0.001; // 물체 바로 앞까지 다가가도 렌더링되도록 최소 거리 축소
                console.log("📸 카메라 근거리 클리핑(NearClip) 설정 완료!");
            }

            // --- 0. WebSocket 설정 (STT 데이터 전송용) ---
            const wsUrl = 'ws://localhost:8080/ws/robot';
            let socket: WebSocket | null = null;
            
            const connectWebSocket = () => {
                try {
                    socket = new WebSocket(wsUrl);
                    socket.onopen = () => {
                        console.log('✅ STT WebSocket 연결 성공');
                        const wsStatus = document.getElementById('text-ws-status');
                        if (wsStatus) {
                            wsStatus.innerText = "🟢 WS 연결됨";
                            wsStatus.style.color = "#00e676";
                        }
                    };
                    socket.onclose = () => {
                        console.log('❌ STT WebSocket 연결 종료. 3초 후 재연결 시도...');
                        const wsStatus = document.getElementById('text-ws-status');
                        if (wsStatus) {
                            wsStatus.innerText = "🔴 WS 끊김";
                            wsStatus.style.color = "#ff5252";
                        }
                        setTimeout(connectWebSocket, 3000);
                    };
                    socket.onerror = (err) => console.error('⚠️ STT WebSocket 에러:', err);
                } catch (e) {
                    console.error('WebSocket 초기화 실패:', e);
                }
            };
            connectWebSocket();

            // --- 1. 다각형 그리기 캔버스 ---
            const polyCanvas = document.createElement('canvas');
            polyCanvas.style.position = 'absolute';
            polyCanvas.style.top = '0';
            polyCanvas.style.left = '0';
            polyCanvas.style.width = '100%';
            polyCanvas.style.height = '100%';
            polyCanvas.style.pointerEvents = 'none';
            polyCanvas.style.zIndex = '1002';
            editorUI.canvasContainer.dom.appendChild(polyCanvas);
            const polyCtx = polyCanvas.getContext('2d');

            const markersContainer = document.createElement('div');
            markersContainer.style.position = 'absolute';
            markersContainer.style.top = '0';
            markersContainer.style.left = '0';
            markersContainer.style.width = '100%';
            markersContainer.style.height = '100%';
            markersContainer.style.pointerEvents = 'none';
            markersContainer.style.zIndex = '1000';
            editorUI.canvasContainer.dom.appendChild(markersContainer);

            // --- 2. 네이티브 UI 패널 ---
            const panel = document.createElement('div');
            panel.style.position = 'absolute';
            panel.style.top = '15px';
            panel.style.right = '85px';
            panel.style.width = '280px';
            panel.style.backgroundColor = '#2c2c2c';
            panel.style.color = '#eeeeee';
            panel.style.padding = '15px';
            panel.style.borderRadius = '8px';
            panel.style.fontFamily = 'sans-serif';
            panel.style.boxShadow = '0 4px 15px rgba(0,0,0,0.5)';
            panel.style.zIndex = '2000';
            panel.style.pointerEvents = 'auto';
            panel.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 12px; font-weight: bold;">
                    <span id="text-db-status" style="color: #4caf50;">📡 DB 자동 연동 대기중...</span>
                    <span id="text-ws-status" style="color: #ff5252;">🔴 WS 끊김</span>
                </div>
                
                <h3 style="margin: 0 0 15px 0; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 8px;">📦 MoveIt 다각형 영역 선택</h3>
                <div style="margin-bottom: 15px;">
                    <button id="btn-poly-toggle" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #5e35b1; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">📐 영역 찍기 모드: OFF</button>
                    <button id="btn-poly-complete" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">✅ 이 다각형으로 영역 추출</button>
                    <button id="btn-reset-boxes" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #546e7a; color: white; border: none; border-radius: 4px; cursor: pointer;">🔄 선택 영역 모두 초기화</button>
                    <button id="btn-send-boxes" style="width: 100%; padding: 10px; background: #e65100; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">PLY 추출 & 백엔드 저장</button>
                </div>

                <h3 style="margin: 20px 0 15px 0; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 8px;">🎯 파지점 (Grasp) 매니저</h3>
                <div style="margin-bottom: 15px;">
                    <button id="btn-toggle-grasp" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #00897b; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">👀 파지점 표시: ON</button>
                </div>
                <div style="margin-bottom: 5px; font-size: 12px; color: #aaa;" id="text-active-grasp">선택된 파지점: 없음</div>
                <button id="btn-send-grasp" style="width: 100%; padding: 10px; background: #00838f; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">선택한 파지점 자세 전송</button>

                <h3 style="margin: 20px 0 15px 0; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 8px;">🎤 음성 명령 (STT)</h3>
                <div style="margin-bottom: 15px;">
                    <button id="btn-stt-toggle" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #1976d2; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">🎙️ 음성 인식 시작</button>
                    <div style="margin-bottom: 5px; font-size: 12px; color: #aaa; min-height: 15px; word-break: break-all;" id="text-stt-result">인식된 텍스트가 여기에 표시됩니다.</div>
                </div>
            `;
            editorUI.canvasContainer.dom.appendChild(panel);

            const btnPolyToggle = document.getElementById('btn-poly-toggle')!;
            const btnPolyComplete = document.getElementById('btn-poly-complete')!;
            const btnResetBoxes = document.getElementById('btn-reset-boxes')!;
            const btnSendBoxes = document.getElementById('btn-send-boxes')!;
            const btnToggleGrasp = document.getElementById('btn-toggle-grasp')!;
            const btnSendGrasp = document.getElementById('btn-send-grasp')!;
            const textActiveGrasp = document.getElementById('text-active-grasp')!;
            const textDbStatus = document.getElementById('text-db-status')!;
            
            const btnSttToggle = document.getElementById('btn-stt-toggle') as HTMLButtonElement;
            const textSttResult = document.getElementById('text-stt-result')!;

            // --- 3. 상태 변수들 ---
            let isPolyMode = false;
            let polygonPoints: {x: number, y: number}[] = [];
            let currentMousePos: {x: number, y: number} | null = null;
            let isPolygonClosed = false;
            let completedPolygons: {x: number, y: number}[][] = [];
            let moveItBoxes: any[] = [];
            let selectedPointIndices = new Set<number>();
            let activeGraspData: any = null;
            let markers: any[] = [];
            let isGraspVisible = true;
            let currentLoadedFileName = ""; // 현재 화면에 로드된 파일명 추적
            let currentLoadedGraspFileName = "";

            // ---------------------------------------------------------
            // 🎙️ STT (음성 인식) 로직 구현
            // ---------------------------------------------------------
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            let recognition: any = null;
            let isRecording = false;

            if (SpeechRecognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false; // 한 번 말하고 끝나면 자동 종료
                recognition.interimResults = false; // 중간 결과 생략 (최종 결과만)
                recognition.lang = 'ko-KR'; // 한국어 설정 (원하면 'en-US' 등으로 변경)

                recognition.onresult = (event: any) => {
                    const transcript = event.results[0][0].transcript;
                    textSttResult.innerText = `💬 "${transcript}"`;
                    textSttResult.style.color = "#00e676";
                    console.log("🎤 음성 인식 결과:", transcript);

                    // 백엔드로 WebSocket 전송
                    if (socket && socket.readyState === WebSocket.OPEN) {
                        const payload = JSON.stringify({ type: 'stt_command', text: transcript });
                        socket.send(payload);
                        console.log("📤 WebSocket 전송 완료:", payload);
                    } else {
                        console.warn("⚠️ WebSocket이 연결되어 있지 않아 서버로 전송하지 못했습니다.");
                        textSttResult.innerText += " (서버 전송 실패)";
                        textSttResult.style.color = "#ffb300";
                    }
                };

                recognition.onerror = (event: any) => {
                    console.error("STT 에러 발생:", event.error);
                    textSttResult.innerText = `⚠️ 에러: ${event.error}`;
                    textSttResult.style.color = "#ff5252";
                    stopStt();
                };

                recognition.onend = () => {
                    stopStt();
                };
            } else {
                btnSttToggle.innerText = "❌ 브라우저 미지원";
                btnSttToggle.style.background = "#424242";
                btnSttToggle.disabled = true;
                textSttResult.innerText = "Chrome 브라우저를 사용해주세요.";
            }

            const startStt = () => {
                if (!recognition) return;
                try {
                    recognition.start();
                    isRecording = true;
                    btnSttToggle.innerText = "🛑 듣는 중... (클릭 시 중지)";
                    btnSttToggle.style.background = "#d32f2f"; // 빨간색
                    textSttResult.innerText = "말씀해 주세요...";
                    textSttResult.style.color = "#aaa";
                } catch(e) {
                    console.error("STT 시작 오류:", e);
                }
            };

            const stopStt = () => {
                if (!recognition) return;
                try {
                    recognition.stop();
                } catch(e) {}
                isRecording = false;
                btnSttToggle.innerText = "🎙️ 음성 인식 시작";
                btnSttToggle.style.background = "#1976d2"; // 파란색
            };

            btnSttToggle.addEventListener('pointerdown', (e) => {
                e.stopPropagation();
                if (isRecording) {
                    stopStt();
                } else {
                    startStt();
                }
            });

            // ---------------------------------------------------------
            // 🌟 4. 데이터 로드 및 갱신 함수 (API 연동)
            // ---------------------------------------------------------
            const backendBaseUrl = 'http://localhost:8080'; // 공통 URL

            const loadLatestData = async () => {
                try {
                    const response = await fetch(`${backendBaseUrl}/api/ply/latest`);
                    
                    if (response.status === 204) return; // 데이터 없음
                    
                    const dbData = await response.json();
                    
                    // ==========================================
                    // 1. PLY 파일 변경 감지 및 로드 (독립 실행)
                    // ==========================================
                    if (dbData && dbData.fileName && dbData.fileName !== currentLoadedFileName) {
                        console.log(`🔄 새로운 스캔 데이터 감지됨: ${dbData.fileName}`);
                        textDbStatus.innerText = `📡 최신 로드됨: ${dbData.fileName}`;
                        textDbStatus.style.color = "#00e676";
                        currentLoadedFileName = dbData.fileName;

                        try {
                            // 🚀 새 파일을 불러오기 전에 화면의 기존 모델(Splat) 및 선택 데이터 모두 지우기
                            const existingElements = (scene as any).elements;
                            if (existingElements && existingElements.length > 0) {
                                
                                // 1. 커스텀 다각형 변수들 비우기
                                selectedPointIndices.clear();
                                moveItBoxes = [];
                                polygonPoints = [];
                                completedPolygons = [];
                                isPolygonClosed = false;
                                
                                // 2. 모델 선택 해제 (기즈모 충돌 방지)
                                try { events.invoke('selection', null); } catch (e) {}

                                // 3. ✨ [핵심] 씬의 "모든 것"을 지우지 않고, "3D 스플랫(PLY)" 데이터만 콕 집어서 골라내기!
                                const splatElements = [...existingElements].filter((el: any) => el.splatData);

                                splatElements.forEach((el: any) => {
                                    try {
                                        if (typeof (scene as any).remove === 'function') {
                                            (scene as any).remove(el); // 오직 PLY 모델만 안전하게 제거
                                        }
                                    } catch (e) {
                                        console.warn("⚠️ 이전 모델 삭제 중 경고:", e);
                                    }
                                });
                                
                                console.log("🧹 이전 스캔 데이터 안전하게 제거 완료");

                                // 4. ✨ [핵심] 렌더링 충돌(RenderPass error)을 막기 위해 0.1초(100ms) 대기하며 프레임 넘겨주기
                                await new Promise(resolve => setTimeout(resolve, 100));
                            }


                            // --- 여기서부터는 기존 코드와 동일합니다 ---
                            const plyFetchUrl = `${backendBaseUrl}/files/${dbData.fileName}?t=${Date.now()}`;
                            const plyRes = await fetch(plyFetchUrl, { cache: 'no-store' });
                            
                            if (!plyRes.ok) throw new Error(`HTTP error! status: ${plyRes.status}`);
                            
                            const plyBlob = await plyRes.blob();
                            const plyFile = new File([plyBlob], dbData.fileName, { type: 'application/octet-stream' });
                            
                            await events.invoke('import', [{ filename: dbData.fileName, contents: plyFile }]);
                            console.log(`✅ ${dbData.fileName} 공유 폴더에서 로드 완료!`);

                            // x축 90도 회전 적용 (방어적 코드)
                            const elements = (scene as any).elements;
                            if (elements && elements.length > 0) {
                                const lastElement = elements.filter((el: any) => el.splatData).pop();
                                if (lastElement) {
                                    const targetEntity = lastElement.setLocalEulerAngles ? lastElement : lastElement.entity;
                                    if (targetEntity && typeof targetEntity.setLocalEulerAngles === 'function') {
                                        targetEntity.setLocalEulerAngles(90, 0, -180); 
                                        console.log(`✅ ${dbData.fileName} x축 90도 회전 적용 완료!`);
                                        scene.forceRender = true;
                                    }
                                }
                            }
                        } catch (err) {
                            console.error("새로운 PLY 로드 실패:", err);
                        }
                    }
                    // ==========================================
                    // 2. 파지점(JSON) 파일 변경 감지 및 로드 (독립 실행)
                    // ==========================================
                    if (dbData && dbData.graspDataFileName && dbData.graspDataFileName !== currentLoadedGraspFileName) {
                        console.log(`🎯 새로운 파지점 데이터 감지됨: ${dbData.graspDataFileName}`);
                        currentLoadedGraspFileName = dbData.graspDataFileName; // 최신 파일명으로 업데이트
            
                        // 기존 파지점 마커 지우기
                        markersContainer.innerHTML = '';
                        markers = [];
                        activeGraspData = null;
                        textActiveGrasp.innerText = "선택된 파지점: 없음";
            
                        // 새로운 파지점 마커 그리기
                        try {
                            const graspUrl = `${backendBaseUrl}/files/${dbData.graspDataFileName}?t=${Date.now()}`;
                            const graspRes = await fetch(graspUrl, { cache: 'no-store' });
                            if (graspRes.ok) {
                                const graspData = await graspRes.json();
                                const graspsList = graspData.valid_grasps || graspData.grasp_points || [];
            
                                graspsList.forEach((point: any) => {
                                    const marker = document.createElement('div');
                                    marker.style.position = 'absolute';
                                    marker.style.width = '4px';
                                    marker.style.height = '4px';
                                    marker.style.marginLeft = '-6px';
                                    marker.style.marginTop = '-6px';
                                    marker.style.borderRadius = '50%';
                                    marker.style.backgroundColor = '#f44336';
                                    marker.style.cursor = 'pointer';
                                    marker.style.pointerEvents = 'auto';
            
                                    const mObj = { dom: marker, pos: { x: point.tcp_x, y: point.tcp_y, z: point.tcp_z }, data: point };
            
                                    marker.addEventListener('pointerdown', (e) => {
                                        e.stopPropagation();
                                        markers.forEach(m => m.dom.style.backgroundColor = '#f44336');
                                        marker.style.backgroundColor = '#00e676';
                                        activeGraspData = point;
                                        textActiveGrasp.innerText = `선택됨: TCP (${point.tcp_x.toFixed(2)}, ${point.tcp_y.toFixed(2)}, ${point.tcp_z.toFixed(2)})`;
                                    });
            
                                    markersContainer.appendChild(marker);
                                    markers.push(mObj);
                                });
                                console.log(`✅ ${dbData.graspDataFileName} 파지점 마커 업데이트 완료!`);
                            }
                        } catch (err) {
                            console.error("새로운 파지점 데이터 로드 실패:", err);
                        }
                    }
                    
                } catch (error) {
                    textDbStatus.innerText = "📡 백엔드 연결 실패";
                    textDbStatus.style.color = "#ff5252";
                }
            };

            await loadLatestData();
            setInterval(loadLatestData, 3000);
            // ---------------------------------------------------------

            // --- 5. 버튼 이벤트 ---
            btnToggleGrasp.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                isGraspVisible = !isGraspVisible;
                markersContainer.style.display = isGraspVisible ? "block" : "none";
                btnToggleGrasp.innerText = isGraspVisible ? "👀 파지점 표시: ON" : "👀 파지점 표시: OFF";
                btnToggleGrasp.style.background = isGraspVisible ? "#00897b" : "#757575";
            });

            btnPolyToggle.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                isPolyMode = !isPolyMode;
                if(isPolyMode) {
                    btnPolyToggle.innerText = "🔒 캔버스 잠금 & 영역 찍기: ON";
                    btnPolyToggle.style.background = "#d81b60";
                    polyCanvas.style.pointerEvents = "auto";
                } else {
                    btnPolyToggle.innerText = "📐 영역 찍기 모드: OFF";
                    btnPolyToggle.style.background = "#5e35b1";
                    polyCanvas.style.pointerEvents = "none";
                    polygonPoints = [];
                    currentMousePos = null;
                    isPolygonClosed = false;
                }
                scene.forceRender = true;
            });

            btnResetBoxes.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                moveItBoxes = [];
                selectedPointIndices.clear();
                polygonPoints = [];
                completedPolygons = [];
                isPolygonClosed = false;
                scene.forceRender = true;
            });

            // ---------------------------------------------------------
            // 🌟 6. [핵심 변경사항] PLY 추출 후 공유 폴더 저장을 위한 백엔드 전송
            // ---------------------------------------------------------
            btnSendBoxes.addEventListener("pointerdown", async (e) => {
                e.stopPropagation();
                
                if (selectedPointIndices.size === 0) {
                    return alert("⚠️ 추출할 영역을 먼저 다각형으로 선택해 주세요!");
                }

                btnSendBoxes.innerText = "⏳ 처리 중...";
                btnSendBoxes.style.background = "#880e4f";

                try {
                    // 1. 현재 선택된 스플랫 모델 및 변환 매트릭스 가져오기
                    let splatTransform = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
                    const elements = (scene as any).elements;
                    let activeSplat = elements && elements.length > 0 ? elements.find((el: any) => el.splatData) : null;
                    
                    if (activeSplat && activeSplat.worldTransform) {
                        splatTransform = activeSplat.worldTransform.data;
                    }

                    if (!activeSplat || !activeSplat.splatData) {
                        throw new Error("3D 모델 데이터를 찾을 수 없습니다.");
                    }

                    let xData = activeSplat.splatData.getProp('x');
                    let yData = activeSplat.splatData.getProp('y');
                    let zData = activeSplat.splatData.getProp('z');

                    // 2. PLY 데이터 형식에 맞게 문자열 생성
                    let plyContent = [];
                    plyContent.push("ply");
                    plyContent.push("format ascii 1.0");
                    plyContent.push(`element vertex ${selectedPointIndices.size}`);
                    plyContent.push("property float x");
                    plyContent.push("property float y");
                    plyContent.push("property float z");
                    plyContent.push("end_header");

                    selectedPointIndices.forEach(idx => {
                        let x = xData[idx]; 
                        let y = yData[idx]; 
                        let z = zData[idx];

                        // Local 좌표를 World 좌표로 변환
                        let worldX = x * splatTransform[0] + y * splatTransform[4] + z * splatTransform[8] + splatTransform[12];
                        let worldY = x * splatTransform[1] + y * splatTransform[5] + z * splatTransform[9] + splatTransform[13];
                        let worldZ = x * splatTransform[2] + y * splatTransform[6] + z * splatTransform[10] + splatTransform[14];

                        plyContent.push(`${worldX.toFixed(6)} ${worldY.toFixed(6)} ${worldZ.toFixed(6)}`);
                    });

                    // 3. 텍스트를 Blob으로 변환하여 파일 껍데기(FormData) 생성
                    const blob = new Blob([plyContent.join('\n')], { type: 'text/plain' });
                    const fileName = `extracted_mesh_${Date.now()}.ply`;
                    
                    const formData = new FormData();
                    formData.append('file', blob, fileName);

                    // 4. 백엔드 API로 파일 전송 (Spring Boot에서 해당 파일을 받아 저장해야 함)
                    // 주의: Spring Boot 컨트롤러에 /api/ply/upload 엔드포인트가 구현되어 있어야 합니다!
                    const uploadUrl = `${backendBaseUrl}/api/ply/upload`; 
                    console.log(`🌐 백엔드로 PLY 파일 전송 시작: ${uploadUrl}`);
                    
                    const response = await fetch(uploadUrl, {
                        method: 'POST',
                        body: formData // 파일 데이터 전송
                    });

                    if (response.ok) {
                        alert(`🎉 PLY 생성 및 전송 완료!\n파일명: ${fileName}\n\n서버의 공유 폴더에 저장되었습니다.`);
                    } else {
                        alert(`⚠️ 백엔드 전송 실패 (상태 코드: ${response.status})`);
                    }

                } catch (error) {
                    console.error("PLY 생성 및 전송 실패:", error);
                    alert("⚠️ 데이터를 처리하거나 서버에 전송하는 중 오류가 발생했습니다.");
                } finally {
                    // 버튼 초기화 및 화면 정리
                    btnSendBoxes.innerText = "PLY 추출 & 백엔드 저장";
                    btnSendBoxes.style.background = "#e65100";
                    
                    moveItBoxes = []; 
                    polygonPoints = [];
                    completedPolygons = []; 
                    isPolygonClosed = false;
                    scene.forceRender = true;
                }
            });

            btnSendGrasp.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                
                if (!activeGraspData) {
                    return alert("⚠️ 빨간색 파지점을 먼저 선택해주세요.");
                }
            
                // 1. 파이썬이 알아들을 수 있게 '이름표(type)'를 붙여서 데이터 포장
                const graspCommand = {
                    type: "execute_grasp", // 파이썬에서 if (msg_type == "execute_grasp") 로 받으면 됩니다.
                    position: [activeGraspData.tcp_x, activeGraspData.tcp_y, activeGraspData.tcp_z],
                    approach_vector: [activeGraspData.approach_dx, activeGraspData.approach_dy, activeGraspData.approach_dz],
                    width: activeGraspData.width
                };
            
                // 2. 웹소켓을 통해 백엔드로 전송 (백엔드가 파이썬으로 브로드캐스트)
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify(graspCommand));
                    
                    // 버튼 UI 피드백
                    btnSendGrasp.innerText = "🚀 파지 명령 전송 완료!";
                    btnSendGrasp.style.background = "#2e7d32"; // 초록색으로 변경
                    setTimeout(() => {
                        btnSendGrasp.innerText = "선택한 파지점 자세 전송";
                        btnSendGrasp.style.background = "#00838f"; // 원래 색으로 복구
                    }, 2000);
                    
                    console.log("📤 파지 명령 웹소켓 전송:", graspCommand);
                } else {
                    alert("⚠️ 서버와 웹소켓이 연결되어 있지 않아 전송할 수 없습니다.");
                }
            });

            // --- 7. 완벽한 화면 잠금 및 다각형 닫기 로직 ---
            const blockEvent = (e: Event) => {
                if(isPolyMode) { e.stopPropagation(); e.preventDefault(); }
            };
            polyCanvas.addEventListener("wheel", blockEvent, {passive: false});
            polyCanvas.addEventListener("contextmenu", blockEvent);
            polyCanvas.addEventListener("dblclick", blockEvent);

            polyCanvas.addEventListener("pointerdown", (e) => {
                if(!isPolyMode) return;
                e.stopPropagation();
                if(e.button !== 0) return;

                if (isPolygonClosed) {
                    polygonPoints = [];
                    isPolygonClosed = false;
                }

                if (polygonPoints.length >= 3) {
                    const dx = e.offsetX - polygonPoints[0].x;
                    const dy = e.offsetY - polygonPoints[0].y;
                    if (dx * dx + dy * dy < 144) {
                        isPolygonClosed = true;
                        currentMousePos = null;
                        scene.forceRender = true;
                        return;
                    }
                }

                polygonPoints.push({ x: e.offsetX, y: e.offsetY });
                scene.forceRender = true;
            });

            polyCanvas.addEventListener("pointermove", (e) => {
                if(!isPolyMode) return;
                e.stopPropagation();
                if (!isPolygonClosed) {
                    currentMousePos = { x: e.offsetX, y: e.offsetY };
                    scene.forceRender = true;
                }
            });

            // --- 8. 초고도 최적화 3D 점 추출 ---
            btnPolyComplete.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                if (polygonPoints.length < 3) return alert("⚠️ 최소 3개의 점을 찍어주세요!");

                const baseCamera = scene.camera.camera;
                const pcCamera = (baseCamera as any).camera || baseCamera;
                const viewProj = (pcCamera as any)._viewProjMat?.data;

                let splatTransform = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
                const elements = (scene as any).elements;
                let activeSplat = elements && elements.length > 0 ? elements.find((el: any) => el.splatData) : null;
                if (!activeSplat) activeSplat = events.invoke('selection');
                if (activeSplat && activeSplat.worldTransform) splatTransform = activeSplat.worldTransform.data;

                if (activeSplat && activeSplat.splatData && viewProj) {
                    let numSplats = activeSplat.splatData.numSplats;
                    let xData = activeSplat.splatData.getProp('x');
                    let yData = activeSplat.splatData.getProp('y');
                    let zData = activeSplat.splatData.getProp('z');

                    if (xData && yData && zData) {
                        const width = polyCanvas.width;
                        const height = polyCanvas.height;

                        let mvp = new Float32Array(16);
                        for (let i = 0; i < 4; i++) {
                            for (let j = 0; j < 4; j++) {
                                mvp[i * 4 + j] =
                                    viewProj[0 * 4 + j] * splatTransform[i * 4 + 0] +
                                    viewProj[1 * 4 + j] * splatTransform[i * 4 + 1] +
                                    viewProj[2 * 4 + j] * splatTransform[i * 4 + 2] +
                                    viewProj[3 * 4 + j] * splatTransform[i * 4 + 3];
                            }
                        }

                        let polyMinX = Math.min(...polygonPoints.map(p => p.x));
                        let polyMaxX = Math.max(...polygonPoints.map(p => p.x));
                        let polyMinY = Math.min(...polygonPoints.map(p => p.y));
                        let polyMaxY = Math.max(...polygonPoints.map(p => p.y));

                        let minX = Infinity, minY = Infinity, minZ = Infinity;
                        let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
                        let count = 0;

                        for (let i = 0; i < numSplats; i++) {
                            let x = xData[i]; let y = yData[i]; let z = zData[i];

                            let clipW = x * mvp[3] + y * mvp[7] + z * mvp[11] + mvp[15];
                            if (clipW < 0.1) continue;

                            let clipX = x * mvp[0] + y * mvp[4] + z * mvp[8] + mvp[12];
                            let clipY = x * mvp[1] + y * mvp[5] + z * mvp[9] + mvp[13];

                            let screenX = ((clipX / clipW) * 0.5 + 0.5) * width;
                            let screenY = ((-clipY / clipW) * 0.5 + 0.5) * height;

                            if (screenX < polyMinX || screenX > polyMaxX || screenY < polyMinY || screenY > polyMaxY) continue;

                            let isInside = false;
                            for (let pi = 0, pj = polygonPoints.length - 1; pi < polygonPoints.length; pj = pi++) {
                                let xi = polygonPoints[pi].x, yi = polygonPoints[pi].y;
                                let xj = polygonPoints[pj].x, yj = polygonPoints[pj].y;
                                let intersect = ((yi > screenY) != (yj > screenY)) && (screenX < (xj - xi) * (screenY - yi) / (yj - yi) + xi);
                                if (intersect) isInside = !isInside;
                            }

                            if (isInside) {
                                let worldX = x * splatTransform[0] + y * splatTransform[4] + z * splatTransform[8] + splatTransform[12];
                                let worldY = x * splatTransform[1] + y * splatTransform[5] + z * splatTransform[9] + splatTransform[13];
                                let worldZ = x * splatTransform[2] + y * splatTransform[6] + z * splatTransform[10] + splatTransform[14];

                                selectedPointIndices.add(i); 
                                minX = Math.min(minX, worldX);
                                minY = Math.min(minY, worldY);
                                minZ = Math.min(minZ, worldZ);
                                maxX = Math.max(maxX, worldX);
                                maxY = Math.max(maxY, worldY);
                                maxZ = Math.max(maxZ, worldZ);
                                count++;
                            }
                        }

                        if (count > 0) {
                            const PADDING = 0.02;
                            moveItBoxes.push({
                                id: "obstacle_poly_" + Date.now().toString().slice(-4),
                                point_count: count,
                                size: [
                                    Number((Math.max(maxX - minX, PADDING)).toFixed(4)),
                                    Number((Math.max(maxY - minY, PADDING)).toFixed(4)),
                                    Number((Math.max(maxZ - minZ, PADDING)).toFixed(4))
                                ],
                                position: [
                                    Number(((maxX + minX) / 2).toFixed(4)),
                                    Number(((maxY + minY) / 2).toFixed(4)),
                                    Number(((maxZ + minZ) / 2).toFixed(4))
                                ]
                            });
                            completedPolygons.push([...polygonPoints]);
                        }
                    }
                }
                polygonPoints = [];
                currentMousePos = null;
                isPolygonClosed = false;
                scene.forceRender = true;
            });

            // --- 9. 렌더링 루프 ---
            events.on('prerender', () => {
                const width = editorUI.canvasContainer.dom.offsetWidth;
                const height = editorUI.canvasContainer.dom.offsetHeight;

                if (polyCanvas.width !== width || polyCanvas.height !== height) {
                    polyCanvas.width = width;
                    polyCanvas.height = height;
                }

                if (polyCtx) {
                    polyCtx.clearRect(0, 0, width, height);

                    completedPolygons.forEach(poly => {
                        polyCtx.beginPath();
                        polyCtx.moveTo(poly[0].x, poly[0].y);
                        for (let i = 1; i < poly.length; i++) polyCtx.lineTo(poly[i].x, poly[i].y);
                        polyCtx.closePath();
                        polyCtx.fillStyle = 'rgba(0, 150, 255, 0.3)';
                        polyCtx.fill();
                        polyCtx.lineWidth = 2;
                        polyCtx.strokeStyle = 'rgba(0, 150, 255, 0.8)';
                        polyCtx.stroke();
                    });

                    if (polygonPoints.length > 0 && isPolyMode) {
                        polyCtx.beginPath();
                        polyCtx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
                        for (let i = 1; i < polygonPoints.length; i++) {
                            polyCtx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
                        }
                        if (isPolygonClosed) {
                            polyCtx.closePath();
                            polyCtx.fillStyle = 'rgba(0, 150, 255, 0.4)';
                            polyCtx.fill();
                        } else {
                            if (currentMousePos) polyCtx.lineTo(currentMousePos.x, currentMousePos.y);
                            polyCtx.fillStyle = 'rgba(0, 150, 255, 0.15)';
                            polyCtx.fill();
                        }

                        polyCtx.lineWidth = 2;
                        polyCtx.strokeStyle = 'rgba(0, 150, 255, 0.8)';
                        polyCtx.stroke();

                        polygonPoints.forEach((p, idx) => {
                            polyCtx.beginPath();
                            let isStartPoint = (idx === 0 && !isPolygonClosed && polygonPoints.length >= 3);
                            polyCtx.arc(p.x, p.y, isStartPoint ? 8 : 4, 0, Math.PI * 2);
                            polyCtx.fillStyle = isStartPoint ? 'yellow' : 'red';
                            polyCtx.fill();
                            if (isStartPoint) {
                                polyCtx.lineWidth = 2;
                                polyCtx.strokeStyle = 'red';
                                polyCtx.stroke();
                            }
                        });
                    }

                    const baseCamera = scene.camera.camera;
                    const pcCamera = (baseCamera as any).camera || baseCamera;
                    const viewProj = (pcCamera as any)._viewProjMat?.data;

                    let splatTransform = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
                    const elements = (scene as any).elements;
                    let activeSplat = elements && elements.length > 0 ? elements.find((el: any) => el.splatData) : null;
                    if (!activeSplat) activeSplat = events.invoke('selection');
                    if (activeSplat && activeSplat.worldTransform) splatTransform = activeSplat.worldTransform.data;

                    if (markersContainer.style.display !== 'none' && viewProj) {
                        markers.forEach(m => {
                            const localX = m.pos.x;
                            const localY = m.pos.y;
                            const localZ = m.pos.z;

                            let worldX = localX * splatTransform[0] + localY * splatTransform[4] + localZ * splatTransform[8] + splatTransform[12];
                            let worldY = localX * splatTransform[1] + localY * splatTransform[5] + localZ * splatTransform[9] + splatTransform[13];
                            let worldZ = localX * splatTransform[2] + localY * splatTransform[6] + localZ * splatTransform[10] + splatTransform[14];

                            let clipX = worldX * viewProj[0] + worldY * viewProj[4] + worldZ * viewProj[8] + viewProj[12];
                            let clipY = worldX * viewProj[1] + worldY * viewProj[5] + worldZ * viewProj[9] + viewProj[13];
                            let clipW = worldX * viewProj[3] + worldY * viewProj[7] + worldZ * viewProj[11] + viewProj[15];

                            if (clipW > 0.1) {
                                m.dom.style.left = `${((clipX / clipW) * 0.5 + 0.5) * width}px`;
                                m.dom.style.top = `${((-clipY / clipW) * 0.5 + 0.5) * height}px`;
                                m.dom.style.display = 'block';
                            } else {
                                m.dom.style.display = 'none';
                            }
                        });
                    }

                    if (selectedPointIndices.size > 0 && activeSplat && activeSplat.splatData && viewProj) {
                        let xData = activeSplat.splatData.getProp('x');
                        let yData = activeSplat.splatData.getProp('y');
                        let zData = activeSplat.splatData.getProp('z');

                        let mvp = new Float32Array(16);
                        for (let i = 0; i < 4; i++) {
                            for (let j = 0; j < 4; j++) {
                                mvp[i * 4 + j] =
                                    viewProj[0 * 4 + j] * splatTransform[i * 4 + 0] +
                                    viewProj[1 * 4 + j] * splatTransform[i * 4 + 1] +
                                    viewProj[2 * 4 + j] * splatTransform[i * 4 + 2] +
                                    viewProj[3 * 4 + j] * splatTransform[i * 4 + 3];
                            }
                        }

                        polyCtx.fillStyle = 'rgba(57, 255, 20, 0.9)';
                        polyCtx.beginPath();

                        selectedPointIndices.forEach(idx => {
                            let x = xData[idx]; let y = yData[idx]; let z = zData[idx];
                            let clipW = x * mvp[3] + y * mvp[7] + z * mvp[11] + mvp[15];
                            if (clipW > 0.1) {
                                let clipX = x * mvp[0] + y * mvp[4] + z * mvp[8] + mvp[12];
                                let clipY = x * mvp[1] + y * mvp[5] + z * mvp[9] + mvp[13];
                                polyCtx.rect(((clipX / clipW) * 0.5 + 0.5) * width - 1, ((-clipY / clipW) * 0.5 + 0.5) * height - 1, 3, 3);
                            }
                        });
                        polyCtx.fill();
                    }
                }
            });

        } catch (error) {
            console.warn("로직 실행 실패:", error);
        }
    }, 1500);
    // =========================================================

};

export { main };