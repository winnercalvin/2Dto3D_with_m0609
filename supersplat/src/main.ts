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
    // 🚀 [커스텀 로직] M0609 파지점 자동 로드 및 시각화
    // =========================================================
    setTimeout(async () => {
        try {
            console.log("🛠️ 파지점 시각화 세팅 시작...");

            // 1. 마커 컨테이너 생성
            const markersContainer = document.createElement('div');
            markersContainer.style.position = 'absolute';
            markersContainer.style.top = '0';
            markersContainer.style.left = '0';
            markersContainer.style.width = '100%';
            markersContainer.style.height = '100%';
            markersContainer.style.pointerEvents = 'none';
            markersContainer.style.zIndex = '1000';
            editorUI.canvasContainer.dom.appendChild(markersContainer);

            // 2. 토글 버튼 생성
            const toggleBtn = document.createElement("button");
            toggleBtn.innerText = "👀 파지점 끄기";
            toggleBtn.style.position = "absolute";
            toggleBtn.style.bottom = "80px";
            toggleBtn.style.left = "10%";
            toggleBtn.style.transform = "translateX(-50%)";
            toggleBtn.style.padding = "10px 20px";
            toggleBtn.style.fontSize = "16px";
            toggleBtn.style.fontWeight = "bold";
            toggleBtn.style.backgroundColor = "#ff5722";
            toggleBtn.style.color = "white";
            toggleBtn.style.border = "none";
            toggleBtn.style.borderRadius = "8px";
            toggleBtn.style.cursor = "pointer";
            toggleBtn.style.zIndex = "1001";
            toggleBtn.style.pointerEvents = "auto";

            let isVisible = true;

            toggleBtn.addEventListener("pointerdown", (e) => {
                e.stopPropagation(); // 부모 요소(캔버스 등)로 이벤트가 퍼지는 것을 막음
                
                isVisible = !isVisible;
                markersContainer.style.display = isVisible ? "block" : "none";
                toggleBtn.innerText = isVisible ? "👀 파지점 끄기" : "👀 파지점 켜기";
                toggleBtn.style.backgroundColor = isVisible ? "#ff5722" : "#4caf50";
                
                console.log("포인터 이벤트 발생!"); // 디버깅용
            });


            editorUI.canvasContainer.dom.appendChild(toggleBtn);

            // 3. JSON 로드 (dist 폴더에 파일이 있어야 함)
            const jsonUrl = new URL('/downsampled_points.json', document.baseURI).toString();
            const response = await fetch(jsonUrl);
            if (!response.ok) throw new Error("JSON 파일을 찾을 수 없습니다.");
            const graspData = await response.json();

            // 4. 마커 동그라미 생성
            const markers: { dom: HTMLDivElement, pos: any }[] = [];
            graspData.grasp_points.forEach((point: any) => {
                const marker = document.createElement('div');
                //marker.innerText = point.rank.toString();
                marker.style.position = 'absolute';
                marker.style.width = '1px';
                marker.style.height = '1px';
                marker.style.marginLeft = '-12px';
                marker.style.marginTop = '-12px';
                marker.style.borderRadius = '50%';
                marker.style.border = '2px solid white';
                marker.style.boxShadow = '0 0 10px rgba(0,0,0,0.8)';
                marker.style.display = 'flex';
                marker.style.alignItems = 'center';
                marker.style.justifyContent = 'center';
                marker.style.color = 'white';
                marker.style.fontWeight = 'bold';
                marker.style.fontSize = '14px';
                marker.style.cursor = 'pointer';
                marker.style.pointerEvents = 'auto';
                marker.style.backgroundColor = 'rgba(255, 0, 0, 0.8)';

                // if (point.rank === 1) marker.style.backgroundColor = 'rgba(0, 255, 0, 0.8)';
                // else if (point.rank === 2) marker.style.backgroundColor = 'rgba(255, 200, 0, 0.8)';
                // else marker.style.backgroundColor = 'rgba(255, 0, 0, 0.8)';

                marker.addEventListener('pointerdown', (e) => {
                    e.stopPropagation(); // 3D 캔버스가 이벤트를 가로채거나 화면이 돌아가는 것을 방지
                    console.log(`🎯 파지점 클릭됨! [Rank: ${point.rank}]`);
                    console.log(`X: ${point.position.x}, Y: ${point.position.y}, Z: ${point.position.z}`);
                    console.log(`NX: ${point.approach_vector.nx}, NY: ${point.approach_vector.ny}, NZ: ${point.approach_vector.nz}`);
                    
                    // 원한다면 alert로 화면에 띄울 수도 있습니다.
                    // alert(`Rank: ${point.rank}\nX: ${point.position.x}\nY: ${point.position.y}\nZ: ${point.position.z}`);
                });

                markersContainer.appendChild(marker);
                markers.push({ dom: marker, pos: point.position });
            });

            // 5. 3D -> 2D 화면 투영 (마커가 점구름을 완벽히 따라다니게 수학적 결합!)
            events.on('prerender', () => {
                if(markersContainer.style.display === 'none') return;
                
                const baseCamera = scene.camera.camera;
                const pcCamera = (baseCamera as any).camera || baseCamera;
                const viewProj = (pcCamera as any)._viewProjMat?.data;
                
                if(!viewProj) return;

                // 🌟 핵심: 로드된 3D 가우시안 모델(파인애플)의 현재 위치/회전/스케일 상태값을 빼옵니다.
                let splatTransform = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]; // 기본값
                
                const elements = (scene as any).elements;
                let activeSplat = null;
                if (elements && elements.length > 0) {
                    activeSplat = elements.find((e: any) => e.splatData);
                }
                if (!activeSplat) {
                    activeSplat = events.invoke('selection'); // 선택된 스플랫 폴백
                }

                if (activeSplat && activeSplat.worldTransform) {
                    splatTransform = activeSplat.worldTransform.data;
                }

                const width = editorUI.canvasContainer.dom.offsetWidth;
                const height = editorUI.canvasContainer.dom.offsetHeight;

                markers.forEach(m => {
                    const localX = m.pos.x;
                    const localY = m.pos.y;
                    const localZ = m.pos.z;

                    // [1단계] 마커의 원본 좌표를 파인애플이 이동/회전한 만큼 똑같이 이동시킵니다 (행렬 곱셈)
                    let worldX = localX * splatTransform[0] + localY * splatTransform[4] + localZ * splatTransform[8] + splatTransform[12];
                    let worldY = localX * splatTransform[1] + localY * splatTransform[5] + localZ * splatTransform[9] + splatTransform[13];
                    let worldZ = localX * splatTransform[2] + localY * splatTransform[6] + localZ * splatTransform[10] + splatTransform[14];

                    // [2단계] 화면에 보이도록 카메라 렌즈 투영
                    let clipX = worldX * viewProj[0] + worldY * viewProj[4] + worldZ * viewProj[8] + viewProj[12];
                    let clipY = worldX * viewProj[1] + worldY * viewProj[5] + worldZ * viewProj[9] + viewProj[13];
                    let clipW = worldX * viewProj[3] + worldY * viewProj[7] + worldZ * viewProj[11] + viewProj[15];

                    if (clipW > 0.1) {
                        const ndcX = clipX / clipW;
                        const ndcY = clipY / clipW;
                        const screenX = (ndcX * 0.5 + 0.5) * width;
                        const screenY = (-ndcY * 0.5 + 0.5) * height; // Y축 반전
                        m.dom.style.left = `${screenX}px`;
                        m.dom.style.top = `${screenY}px`;
                        m.dom.style.display = 'flex';
                    } else {
                        m.dom.style.display = 'none'; // 등 뒤로 가면 숨김
                    }
                });
            });

            // 6. PLY 자동 로드 (dist 폴더에 파일이 있어야 함)
            const plyUrl = new URL('/point_cloud.ply', document.baseURI).toString();
            events.invoke('import', [{
                filename: 'point_cloud.ply',
                url: plyUrl
            }]);

        } catch (error) {
            console.warn("파지점 로드 실패:", error);
        }
    }, 1500); 
    // =========================================================

};

export { main };