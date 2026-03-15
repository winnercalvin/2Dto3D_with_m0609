import os
import time
import torch
import numpy as np
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms
import json    # 🔥 JSON 수정을 위해 추가
import shutil  # 🔥 파일 이동/복사를 위해 추가

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from transformers import AutoModelForImageSegmentation, AutoProcessor, AutoModelForCausalLM
from transformers import SamModel, SamProcessor, CLIPVisionModelWithProjection, CLIPProcessor
import transformers.dynamic_module_utils

class FeatureExtractorNode(Node):
    def __init__(self):
        super().__init__('feature_extractor_node')
        
        self.base_dir = '/home/rokey/robot_share'
        self.input_dir = os.path.join(self.base_dir, 'dt') # 원본 데이터 폴더
        
        # 🔥 [수정됨] 3dgs_workspace 기반 폴더 구조 설정
        self.workspace_dir = os.path.join(self.base_dir, '3dgs_workspace')
        self.mask_dir = self.workspace_dir  # 기존 images 폴더 삭제, 바로 workspace로 지정
        self.feature_dir = os.path.join(self.workspace_dir, 'features') # 기존 Feature_pt 유지
        
        # 폴더 생성
        os.makedirs(self.workspace_dir, exist_ok=True)
        os.makedirs(self.feature_dir, exist_ok=True)
        
        self.is_scanning = False
        self.current_img_idx = 0
        
        self.trigger_sub = self.create_subscription(
            Bool, '/trigger_eod_scan', self.trigger_callback, 10
        )
        self.start_3dgs_pub = self.create_publisher(Bool, '/start_3dgs', 10)
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.get_logger().info(f"⏳ 대규모 AI 모델 로딩 중... (압축 없는 성능 100% 모드!)")
        
        if not hasattr(transformers.dynamic_module_utils, '_is_patched'):
            _orig_get_imports = transformers.dynamic_module_utils.get_imports
            def _safe_get_imports(filename):
                imports = _orig_get_imports(filename)
                if "flash_attn" in imports: imports.remove("flash_attn")
                return imports
            transformers.dynamic_module_utils.get_imports = _safe_get_imports
            transformers.dynamic_module_utils._is_patched = True

        self.model_biref = AutoModelForImageSegmentation.from_pretrained('zhengpeng7/BiRefNet', trust_remote_code=True).cpu().float().eval()
        self.flo_model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-large-ft", trust_remote_code=True).cpu().eval()
        self.flo_processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large-ft", trust_remote_code=True)
        self.sam_model = SamModel.from_pretrained("facebook/sam-vit-base").cpu().eval()
        self.sam_processor = SamProcessor.from_pretrained("facebook/sam-vit-base")
        self.clip_model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-base-patch16").cpu().eval()
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
        
        self.get_logger().info("✅ 성능 100% AI 모델 램(RAM) 로드 완료! 스캔 명령 대기 중...")
        self.timer = self.create_timer(0.5, self.process_next_image)

    def trigger_callback(self, msg):
        if msg.data and not self.is_scanning:
            self.get_logger().warn("🚨 스캔 시작 신호 수신! 이미지 실시간 추출 파이프라인 가동!")
            self.is_scanning = True
            self.current_img_idx = 0

    def process_next_image(self):
        if not self.is_scanning:
            return

        target_filename = f"img_{self.current_img_idx:04d}.jpg"
        target_path = os.path.join(self.input_dir, target_filename)

        if os.path.exists(target_path):
            try:
                time.sleep(0.1) 
                self.get_logger().info(f"⚙️ 처리 중: {target_filename} (640x480 변환)")
                self.run_ai_pipeline(target_path, target_filename)
                self.current_img_idx += 1
            except Exception as e:
                self.get_logger().error(f"이미지 읽기 오류 (재시도 예정): {e}")
        else:
            json_path = os.path.join(self.input_dir, "transforms_train.json")
            if os.path.exists(json_path):
                self.get_logger().info(f"🎉 스캔 및 AI 마스킹 처리 종료! (총 {self.current_img_idx}장)")
                
                # =======================================================
                # 🔥 [수정됨] 최종 폴더 구조 재배치 및 JSON 수정 작업 시작
                # =======================================================
                self.get_logger().info("📦 3DGS를 위한 Workspace 파일 포장 및 JSON 수정 중...")
                
                # 1. transforms_train.json 읽어오기
                with open(json_path, 'r') as f:
                    transform_data = json.load(f)
                
                # 2. JSON 내용 중 file_path를 "img_xxxx.png" 로 변경 (images/ 제거)
                if 'frames' in transform_data:
                    for frame in transform_data['frames']:
                        old_path = frame.get('file_path', '')
                        # 기존 경로에서 파일 이름(img_0000)만 추출
                        base_name = os.path.splitext(os.path.basename(old_path))[0] 
                        # 새로운 png 경로로 덮어쓰기 (앞에 아무것도 안 붙임)
                        frame['file_path'] = f"{base_name}.png"
                
                # 🔥 [NEW] JSON 파일 최상위 데이터에 ply_file_path 정보 추가
                transform_data["ply_file_path"] = "points3D.ply"
                
                # 3. 수정된 JSON을 3dgs_workspace 안에 "transforms.json"으로 저장
                new_json_path = os.path.join(self.workspace_dir, "transforms.json")
                with open(new_json_path, 'w') as f:
                    json.dump(transform_data, f, indent=4)
                    
                # 4. points3D.ply 파일 복사 (dt -> 3dgs_workspace)
                old_ply_path = os.path.join(self.input_dir, "points3D.ply")
                new_ply_path = os.path.join(self.workspace_dir, "points3D.ply")
                if os.path.exists(old_ply_path):
                    shutil.copy2(old_ply_path, new_ply_path)

                self.get_logger().info("✅ 3DGS Workspace 구조 세팅 완벽 완료!")
                # =======================================================

                # 모든 정리가 끝난 후 3DGS 노드 호출
                msg = Bool()
                msg.data = True
                self.start_3dgs_pub.publish(msg)
                self.get_logger().info("🚀 /start_3dgs 토픽 발송 완료! 3DGS 노드를 깨웁니다.")
                
                self.is_scanning = False

    def run_ai_pipeline(self, img_path, fname):
        raw_img = Image.open(img_path).convert("RGB").resize((640, 480), Image.BILINEAR)
        W, H = raw_img.size

        # [Step A] BiRefNet
        self.model_biref.to(self.device) 
        transform_img = transforms.Compose([
            transforms.Resize((1024, 1024)), transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        with torch.no_grad():
            preds = self.model_biref(transform_img(raw_img).unsqueeze(0).to(self.device))[-1].sigmoid().cpu()
        self.model_biref.to('cpu') 
        torch.cuda.empty_cache()   

        biref_mask = transforms.ToPILImage()(preds[0].squeeze()).resize((W, H), Image.BILINEAR)
        final_png = raw_img.copy()
        final_png.putalpha(biref_mask)
        
        # 🔥 여기서 이미지는 3dgs_workspace 폴더에 직접 .png로 예쁘게 저장됩니다.
        final_png.save(os.path.join(self.mask_dir, os.path.splitext(fname)[0] + ".png"))

        white_bg = Image.new("RGB", (W, H), (255, 255, 255))
        white_bg.paste(raw_img, mask=biref_mask)
        masked_img_for_ai = white_bg

        # [Step B] Florence-2 & SAM
        self.flo_model.to(self.device) 
        inputs = self.flo_processor(text="<CAPTION_TO_PHRASE_GROUNDING> red wire", images=masked_img_for_ai, return_tensors="pt").to(self.device)
        with torch.no_grad():
            gen_ids = self.flo_model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"], max_new_tokens=1024)
        gen_text = self.flo_processor.batch_decode(gen_ids, skip_special_tokens=False)[0]
        parsed = self.flo_processor.post_process_generation(gen_text, task="<CAPTION_TO_PHRASE_GROUNDING>", image_size=(W, H))
        self.flo_model.to('cpu') 

        boxes = parsed["<CAPTION_TO_PHRASE_GROUNDING>"].get('bboxes', [])
        if len(boxes) > 0:
            best_index = min(range(len(boxes)), key=lambda i: (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1]))
            best_box = boxes[best_index]
            self.sam_model.to(self.device) 
            sam_inputs = self.sam_processor(masked_img_for_ai, input_boxes=[[[best_box]]], return_tensors="pt").to(self.device)
            with torch.no_grad():
                sam_outputs = self.sam_model(**sam_inputs)
            masks = self.sam_processor.image_processor.post_process_masks(sam_outputs.pred_masks.cpu(), sam_inputs["original_sizes"].cpu(), sam_inputs["reshaped_input_sizes"].cpu())
            red_wire_mask_np = masks[0][0][0].numpy().astype(np.float32)
            self.sam_model.to('cpu') 
        else:
            red_wire_mask_np = np.zeros((H, W), dtype=np.float32)

        torch.cuda.empty_cache() 
        red_wire_mask_torch = torch.from_numpy(red_wire_mask_np).to(self.device)

        # [Step C] CLIP
        self.clip_model.to(self.device) 
        clip_inputs = self.clip_processor(images=raw_img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            clip_outputs = self.clip_model(**clip_inputs)
            feat_map = clip_outputs.last_hidden_state[:, 1:, :].permute(0, 2, 1).view(1, 768, 14, 14)
            proj_weight = self.clip_model.visual_projection.weight[:512, :]
            feat_map_512 = F.conv2d(feat_map, proj_weight.unsqueeze(-1).unsqueeze(-1))
            feat_map_resised = F.interpolate(feat_map_512, size=(H, W), mode='bilinear', align_corners=False).squeeze(0)
        self.clip_model.to('cpu') 
        torch.cuda.empty_cache()  

        final_feature = feat_map_resised * red_wire_mask_torch.unsqueeze(0)
        final_tensor = torch.cat([final_feature, red_wire_mask_torch.unsqueeze(0)], dim=0).cpu()
        
        # 피처 데이터는 기존대로 3dgs_workspace/features 폴더에 .pt로 저장됩니다.
        torch.save(final_tensor, os.path.join(self.feature_dir, os.path.splitext(fname)[0] + ".pt"))

        # ===================================================================
        # 🔥 [NEW] 진짜 정답지(Anchor Vector) 몰래 빼돌리기!
        # ===================================================================
        if red_wire_mask_torch.sum() > 0:
            # 1. 마스크가 칠해진 부분의 512차원 특징만 쏙 빼서 평균을 냅니다.
            anchor_vector = final_feature[:, red_wire_mask_torch > 0].mean(dim=1)
            # 2. 정규화(Normalize)
            anchor_vector = F.normalize(anchor_vector, p=2, dim=0)
            
            # 3. [경로 수정됨] 3dgs_outputs 폴더에 'red_wire_answer.pt' 저장!
            output_dir_path = os.path.join(self.base_dir, '3dgs_outputs')
            os.makedirs(output_dir_path, exist_ok=True) # 폴더가 없으면 자동 생성
            
            answer_path = os.path.join(output_dir_path, "red_wire_answer.pt")
            torch.save(anchor_vector, answer_path)
            
            self.get_logger().info(f"🎯 빨간 선 정답지 저장 완료: {answer_path}")
        # ===================================================================
        
def main(args=None):
    rclpy.init(args=args)
    node = FeatureExtractorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()