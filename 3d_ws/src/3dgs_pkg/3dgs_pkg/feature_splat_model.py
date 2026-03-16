import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import Parameter
from dataclasses import dataclass, field
from typing import Dict, Type, List
from nerfstudio.models.splatfacto import SplatfactoModel, SplatfactoModelConfig
from gsplat.rendering import rasterization

@dataclass
class FeatureSplatfactoModelConfig(SplatfactoModelConfig):
    _target: Type = field(default_factory=lambda: FeatureSplatfactoModel)
    feature_dim: int = 512
    feature_loss_weight: float = 0.1

class FeatureSplatfactoModel(SplatfactoModel):
    config: FeatureSplatfactoModelConfig

    def populate_modules(self):
        super().populate_modules()
        
        # 🔥 1. 고정된 배열 대신, 점들의 XYZ 위치로부터 피처를 동적 생성하는 발전기(MLP) 도입!
        self.feature_generator = nn.Sequential(
            nn.Linear(3, 64),
            nn.ReLU(),
            nn.Linear(64, self.config.feature_dim)
        )
        
        self.feature_encoder = nn.Linear(self.config.feature_dim, 3)
        
        self.feature_decoder = nn.Sequential(
            nn.Linear(3, 64),
            nn.ReLU(),
            nn.Linear(64, self.config.feature_dim)
        )

    # 🔥 2. 파이프라인(옵티마이저)이 새로운 발전기를 찾을 수 있도록 연결
    def get_param_groups(self) -> Dict[str, List[Parameter]]:
        param_groups = super().get_param_groups()
        param_groups["semantic_features"] = list(self.feature_generator.parameters()) + \
                                            list(self.feature_encoder.parameters()) + \
                                            list(self.feature_decoder.parameters())
        return param_groups

    def get_outputs(self, camera):
        outputs = super().get_outputs(camera)
        
        if self.training or "semantic_feature" in outputs:
            # 🔥 3. 현재 살아있는 가우시안 점들의 개수만큼 피처를 실시간 생성!
            # detach()를 써서 3D 공간의 점들 위치가 꼬이지 않도록 보호합니다.
            semantic_features = self.feature_generator(self.means.detach()) 
            compressed_features = self.feature_encoder(semantic_features)
            
            camera_downscale = self._get_downscale_factor()
            camera.rescale_output_resolution(1 / camera_downscale)
            
            W, H = camera.width.item(), camera.height.item()
            
            c2w = camera.camera_to_worlds.squeeze() 
            c2w_4x4 = torch.eye(4, device=c2w.device)
            c2w_4x4[:3, :4] = c2w 
            
            viewmat = torch.linalg.inv(c2w_4x4) 
            K = camera.get_intrinsics_matrices().squeeze() 
            
            target_device = self.means.device
            viewmat = viewmat.to(target_device).unsqueeze(0)
            K = K.to(target_device).unsqueeze(0)
            
            # 🔥 4. 엔진이 요구하는 완벽한 4차원 포맷 [카메라(1), 포인트(N), SH(1), RGB(3)]
            colors_4d = compressed_features.view(1, -1, 1, 3)
            
            rendered_compressed, _, _ = rasterization(
                means=self.means, 
                quats=self.quats, 
                scales=torch.exp(self.scales), 
                opacities=torch.sigmoid(self.opacities).flatten(), 
                colors=colors_4d, 
                viewmats=viewmat, 
                Ks=K, 
                width=W, 
                height=H,
                sh_degree=0,
                packed=False
            )
            
            rendered_512_features = self.feature_decoder(rendered_compressed)
            
            if rendered_512_features.dim() == 4:
                rendered_512_features = rendered_512_features.squeeze(0)
                
            outputs["rendered_features"] = rendered_512_features
            camera.rescale_output_resolution(camera_downscale)
            
        return outputs

    def get_loss_dict(self, outputs, batch, metrics_dict=None) -> Dict[str, torch.Tensor]:
        loss_dict = super().get_loss_dict(outputs, batch, metrics_dict)
        
        if "semantic_feature" in batch and batch["semantic_feature"] is not None:
            if "rendered_features" in outputs:
                target_device = self.means.device
                gt_features = batch["semantic_feature"].to(target_device).float()
                pred_features = outputs["rendered_features"].float()
                
                if pred_features.dim() == 4:
                    pred_f = pred_features.permute(0, 3, 1, 2)
                else:
                    pred_f = pred_features.permute(2, 0, 1).unsqueeze(0)
                
                gt_f = gt_features.permute(2, 0, 1).unsqueeze(0)

                if gt_f.shape[-2:] != pred_f.shape[-2:]:
                    gt_f = F.interpolate(
                        gt_f, 
                        size=(pred_f.shape[2], pred_f.shape[3]), 
                        mode="bilinear", 
                        align_corners=False
                    )
                
                pred_norm = F.normalize(pred_f, dim=1)
                gt_norm = F.normalize(gt_f, dim=1)
                
                cosine_sim = torch.sum(pred_norm * gt_norm, dim=1)
                feature_loss = 1.0 - cosine_sim.mean()
                
                loss_dict["feature_loss"] = feature_loss * self.config.feature_loss_weight
                
        return loss_dict