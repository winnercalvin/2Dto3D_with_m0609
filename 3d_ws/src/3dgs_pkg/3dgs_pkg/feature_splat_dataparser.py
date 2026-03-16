import torch
import torch.nn.functional as F
from pathlib import Path
from typing import Dict
from nerfstudio.data.datasets.base_dataset import InputDataset

class FeatureDataset(InputDataset):
    def __init__(self, dataparser_outputs, scale_factor: float = 1.0):
        super().__init__(dataparser_outputs, scale_factor)
        
        # images 폴더 안에 이미지가 있으므로 .parent.parent 사용
        if len(self.image_filenames) > 0:
            self.feature_dir = self.image_filenames[0].parent.parent / "features"
        else:
            self.feature_dir = None

    def get_metadata(self, data: Dict) -> Dict:
        metadata = {}
        if self.feature_dir is None:
            return metadata
        
        image_idx = data["image_idx"]
        image_path = self.image_filenames[image_idx]
        
        pt_filename = image_path.with_suffix('.pt').name
        pt_path = self.feature_dir / pt_filename
        
        if pt_path.exists():
            feature_tensor = torch.load(pt_path, map_location="cpu")
            
            if feature_tensor.dim() == 3 and feature_tensor.shape[0] == 512:
                # 메모리 다이어트: 해상도 1/4 축소
                feature_tensor = feature_tensor.unsqueeze(0) 
                feature_tensor = F.interpolate(
                    feature_tensor, 
                    scale_factor=0.25, 
                    mode="bilinear", 
                    align_corners=False
                )
                feature_tensor = feature_tensor.squeeze(0) 
                
                # 형태 변경 [H, W, C]
                feature_tensor = feature_tensor.permute(1, 2, 0)
                
            # Float16(Half)으로 변환하여 RAM 사용량 절반으로 감소
            metadata["semantic_feature"] = feature_tensor.half()
        else:
            metadata["semantic_feature"] = None
            
        return metadata