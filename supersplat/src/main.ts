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
    // 🚀 [커스텀 로직] 전송 후 파란색 다각형만 지우고 초록색 점은 유지!
    // =========================================================
    setTimeout(async () => {
        try {
            console.log("🛠️ 초고속 클릭 다각형 영역 선택 UI 세팅 시작...");

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
                <h3 style="margin: 0 0 15px 0; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 8px;">📦 MoveIt 다각형 영역 선택</h3>
                <div style="margin-bottom: 15px;">
                    <button id="btn-poly-toggle" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #5e35b1; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">📐 영역 찍기 모드: OFF</button>
                    <button id="btn-poly-complete" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">✅ 이 다각형으로 영역 추출</button>
                    <button id="btn-reset-boxes" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #546e7a; color: white; border: none; border-radius: 4px; cursor: pointer;">🔄 선택 영역 모두 초기화</button>
                    <button id="btn-send-boxes" style="width: 100%; padding: 10px; background: #e65100; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">전체 선택영역 MoveIt 보내기</button>
                </div>

                <h3 style="margin: 20px 0 15px 0; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 8px;">🎯 파지점 (Grasp) 매니저</h3>
                <div style="margin-bottom: 15px;">
                    <button id="btn-toggle-grasp" style="width: 100%; padding: 8px; margin-bottom: 8px; background: #00897b; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">👀 파지점 표시: ON</button>
                </div>
                <div style="margin-bottom: 5px; font-size: 12px; color: #aaa;" id="text-active-grasp">선택된 파지점: 없음</div>
                <button id="btn-send-grasp" style="width: 100%; padding: 10px; background: #00838f; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">선택한 파지점 자세 전송</button>
            `;
            editorUI.canvasContainer.dom.appendChild(panel);

            const btnPolyToggle = document.getElementById('btn-poly-toggle')!;
            const btnPolyComplete = document.getElementById('btn-poly-complete')!;
            const btnResetBoxes = document.getElementById('btn-reset-boxes')!;
            const btnSendBoxes = document.getElementById('btn-send-boxes')!;
            const btnToggleGrasp = document.getElementById('btn-toggle-grasp')!;
            const btnSendGrasp = document.getElementById('btn-send-grasp')!;
            const textActiveGrasp = document.getElementById('text-active-grasp')!;

            // --- 3. 상태 변수들 ---
            let isPolyMode = false;
            let polygonPoints: {x: number, y: number}[] = [];
            let currentMousePos: {x: number, y: number} | null = null;
            let isPolygonClosed = false;
            let completedPolygons: {x: number, y: number}[][] = [];
            let moveItBoxes: any[] = [];
            let selectedPointIndices = new Set<number>();
            let activeGraspData: any = null;
            const markers: any[] = [];
            let isGraspVisible = true;

            // --- 4. JSON 다운로드 (캐시 무효화 및 새로운 데이터 구조 매핑) ---
            const jsonUrl1 = new URL(`/downsampled_points.json?t=${Date.now()}`, document.baseURI).toString();
            const jsonUrl2 = new URL(`/grasp_points.json?t=${Date.now()}`, document.baseURI).toString();
            const response = await fetch(jsonUrl1, { cache: 'no-store' }).catch(() => fetch(jsonUrl2, { cache: 'no-store' }));
            let graspData: any = {};
            if (response && response.ok) graspData = await response.json();

            // 🌟 수정포인트: valid_grasps 배열로 데이터 접근
            const graspsList = graspData.valid_grasps || graspData.grasp_points || [];

            graspsList.forEach((point: any, index: number) => {
                const marker = document.createElement('div');
                marker.style.position = 'absolute';
                marker.style.width = '4px';
                marker.style.height = '4px';
                marker.style.marginLeft = '-6px';
                marker.style.marginTop = '-6px';
                marker.style.borderRadius = '50%';
                marker.style.backgroundColor = '#f44336';
                //marker.style.border = '2px solid white';
                marker.style.cursor = 'pointer';
                marker.style.pointerEvents = 'auto';

                // 🌟 수정포인트: point.tcp_x, tcp_y, tcp_z를 3D 공간 투영용으로 매핑
                const mObj = { dom: marker, pos: { x: point.tcp_x, y: point.tcp_y, z: point.tcp_z }, data: point };

                marker.addEventListener('pointerdown', (e) => {
                    e.stopPropagation();
                    markers.forEach(m => m.dom.style.backgroundColor = '#f44336');
                    marker.style.backgroundColor = '#00e676';
                    activeGraspData = point;
                    // 🌟 수정포인트: UI 텍스트 업데이트
                    textActiveGrasp.innerText = `선택됨: TCP (${point.tcp_x.toFixed(2)}, ${point.tcp_y.toFixed(2)}, ${point.tcp_z.toFixed(2)})`;
                });

                markersContainer.appendChild(marker);
                markers.push(mObj);
            });

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

            // 🌟 5-1. 완전 초기화 (초록색 점, 파란색 면 모두 삭제)
            btnResetBoxes.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                moveItBoxes = [];
                selectedPointIndices.clear(); // 초록색 점 날림
                polygonPoints = [];
                completedPolygons = []; // 파란색 면 날림
                isPolygonClosed = false;
                scene.forceRender = true;
            });

            // 🌟 5-2. 전송 버튼 (데이터만 빼고, 파란색 면만 삭제, 초록색 점은 유지!)
            btnSendBoxes.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                if (moveItBoxes.length === 0) return alert("⚠️ 지정된 선택 영역이 없습니다.");
                alert(`[MoveIt 충돌 객체 등록]\n총 ${moveItBoxes.length}개 영역 전송 완료!\n\n` + JSON.stringify(moveItBoxes, null, 2));
                // --- 핵심 패치 ---
                moveItBoxes = []; // 전송했으니 박스 데이터는 초기화 (새로운 작업을 위해)
                polygonPoints = [];
                completedPolygons = []; // 파란색 다각형 껍데기들 초기화!
                isPolygonClosed = false;
                // 💡 selectedPointIndices.clear(); <-- 이 줄을 지웠습니다! 초록색 점은 영구 유지됨!
                scene.forceRender = true;
                console.log("🧹 전송 완료: 파란색 다각형은 지워졌으나, 초록색 포인트는 작업 내역으로 유지됩니다.");
            });

            btnSendGrasp.addEventListener("pointerdown", (e) => {
                e.stopPropagation();
                if (!activeGraspData) return alert("⚠️ 빨간색 파지점을 선택해주세요.");
                // 🌟 수정포인트: 제공된 새로운 데이터 키(approach_dx 등)를 사용하여 JSON 구성
                alert(`[MoveIt 파지 자세 전송]\n\n` + JSON.stringify({
                    id: "target_grasp_pose",
                    position: [activeGraspData.tcp_x, activeGraspData.tcp_y, activeGraspData.tcp_z],
                    approach_vector: [activeGraspData.approach_dx, activeGraspData.approach_dy, activeGraspData.approach_dz],
                    width: activeGraspData.width
                }, null, 2));
            });

            // --- 6. 완벽한 화면 잠금 및 다각형 닫기 로직 ---
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

            // --- 7. 초고도 최적화 3D 점 추출 ---
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

                                selectedPointIndices.add(i); // 🌟 초록 점 데이터 영구 추가
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
                            console.log(`✅ 고속 추출 완료: ${count}개 포인트 포함`);
                        } else {
                            alert("⚠️ 다각형 영역 내부에 포인트가 없습니다.");
                        }
                    }
                }
                polygonPoints = [];
                currentMousePos = null;
                isPolygonClosed = false;
                scene.forceRender = true;
            });

            // --- 8. 렌더링 루프 ---
            events.on('prerender', () => {
                const width = editorUI.canvasContainer.dom.offsetWidth;
                const height = editorUI.canvasContainer.dom.offsetHeight;

                if (polyCanvas.width !== width || polyCanvas.height !== height) {
                    polyCanvas.width = width;
                    polyCanvas.height = height;
                }

                if (polyCtx) {
                    polyCtx.clearRect(0, 0, width, height);

                    // 완료된 다각형 렌더링
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

                    // 현재 그리고 있는 다각형 렌더링
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

                    // 파지점 마커 위치
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

                    // 선택된 3D 점 네온 그린 오버레이
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

                // 🌟 9. PLY 강제 다운로드
                try {
                    const plyFetchUrl = new URL(`/point_cloud.ply?t=${Date.now()}`, document.baseURI).toString();
                    const plyRes = await fetch(plyFetchUrl, { cache: 'no-store' });
                    const plyBlob = await plyRes.blob();
                    const plyFile = new File([plyBlob], 'point_cloud.ply', { type: 'application/octet-stream' });
                    events.invoke('import', [{ filename: 'point_cloud.ply', contents: plyFile }]);
                } catch (err) {
                    console.error("PLY 강제 로드 실패:", err);
                }

            } catch (error) {
                console.warn("로직 실행 실패:", error);
            }
        }, 1500);
        // =========================================================

    };

    export { main };