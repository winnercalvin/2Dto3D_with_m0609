import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'eod_detection'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        
        # 🔥 이 줄이 핵심입니다! launch 폴더의 파일들을 설치 경로로 복사해 줍니다.
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rokey',
    maintainer_email='rokey@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'analyzer_node = eod_detection.analyzer_node:main',
            'scanner_node = eod_detection.scanner_node:main',
            'feature_extractor_node = eod_detection.feature_extractor_node:main',
            'manipulator_node = eod_detection.manipulator_node:main',
        ],
    },
)