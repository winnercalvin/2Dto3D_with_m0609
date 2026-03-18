from setuptools import find_packages, setup
import os
from glob import glob

package_name = '3dgs_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'train_node = 3dgs_pkg.train_node:main',
            'feature = 3dgs_pkg.train_node_feature:main',
            'ply_to_obj_node = 3dgs_pkg.ply_to_obj_node:main',
            'whisper_stt_node = 3dgs_pkg.stt_whisper_node:main',
            'enhanced_mediapipe_pose = 3dgs_pkg.enhanced_mediapipe_pose:main'
        ],
        'nerfstudio.method_configs': [
            'feature-splatfacto = 3dgs_pkg.feature_splat_config:feature_splat_method'
        ],
    },
)
