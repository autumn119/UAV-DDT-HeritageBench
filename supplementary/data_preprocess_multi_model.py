#!/usr/bin/env python3
"""
Multi-model data preprocessing script.
Supports: 2DGS, Instant-NGP, NeRF.
Features: image downsampling, format conversion, COLMAP pose estimation, dataset splitting.

Usage:
    python data_preprocess_multi_model.py --input /path/to/images --output /path/to/output --model 2dgs --mode all
    python data_preprocess_multi_model.py --input /path/to/images --output /path/to/output --model instant-ngp --mode all
    python data_preprocess_multi_model.py --input /path/to/images --output /path/to/output --model nerf --mode all
"""

import os
import sys
import argparse
import shutil
import json
import subprocess
import struct
from pathlib import Path
from PIL import Image
import numpy as np
from typing import Dict, List, Tuple, Optional


def read_colmap_binary(sparse_dir: Path) -> Tuple[Dict, Dict]:
    """Read COLMAP binary-format camera and image data."""
    cameras = {}
    images = {}

    CAMERA_MODEL_PARAMS = {
        0: 3,   # SIMPLE_PINHOLE: f, cx, cy
        1: 4,   # PINHOLE: fx, fy, cx, cy
        2: 4,   # SIMPLE_RADIAL: f, cx, cy, k
        3: 5,   # RADIAL: f, cx, cy, k1, k2
        4: 8,   # OPENCV: fx, fy, cx, cy, k1, k2, p1, p2
        5: 12,  # OPENCV_FISHEYE
        6: 5,   # FULL_OPENCV (partial)
    }

    cameras_file = sparse_dir / "cameras.bin"
    if cameras_file.exists():
        with open(cameras_file, 'rb') as f:
            num_cameras = struct.unpack('<Q', f.read(8))[0]
            for _ in range(num_cameras):
                camera_id = struct.unpack('<I', f.read(4))[0]
                model_id = struct.unpack('<I', f.read(4))[0]
                width = struct.unpack('<Q', f.read(8))[0]
                height = struct.unpack('<Q', f.read(8))[0]
                num_params = CAMERA_MODEL_PARAMS.get(model_id, 4)
                params = struct.unpack('<' + 'd' * num_params, f.read(8 * num_params))
                cameras[camera_id] = {
                    'model': model_id, 'width': width, 'height': height, 'params': params
                }

    images_file = sparse_dir / "images.bin"
    if images_file.exists():
        with open(images_file, 'rb') as f:
            num_images = struct.unpack('<Q', f.read(8))[0]
            for _ in range(num_images):
                image_id = struct.unpack('<I', f.read(4))[0]
                qvec = struct.unpack('<dddd', f.read(32))
                tvec = struct.unpack('<ddd', f.read(24))
                camera_id = struct.unpack('<I', f.read(4))[0]
                name = ''
                while True:
                    char = f.read(1)
                    if char == b'\x00':
                        break
                    name += char.decode('utf-8')
                num_points2D = struct.unpack('<Q', f.read(8))[0]
                for _ in range(num_points2D):
                    f.read(24)
                images[image_id] = {
                    'qvec': qvec, 'tvec': tvec, 'camera_id': camera_id, 'name': name
                }

    return cameras, images


def parse_camera_params(camera: Dict) -> Tuple[float, float, float, float]:
    """Parse fl_x, fl_y, cx, cy from camera model parameters."""
    model_id = camera['model']
    params = camera['params']
    if model_id in (0,):        # SIMPLE_PINHOLE: f, cx, cy
        return params[0], params[0], params[1], params[2]
    elif model_id in (1,):      # PINHOLE: fx, fy, cx, cy
        return params[0], params[1], params[2], params[3]
    elif model_id in (2,):      # SIMPLE_RADIAL: f, cx, cy, k
        return params[0], params[0], params[1], params[2]
    elif model_id in (3,):      # RADIAL: f, cx, cy, k1, k2
        return params[0], params[0], params[1], params[2]
    elif model_id in (4,):      # OPENCV: fx, fy, cx, cy, ...
        return params[0], params[1], params[2], params[3]
    else:
        return params[0], params[0], camera['width'] / 2, camera['height'] / 2


def quat_to_rotation(qw, qx, qy, qz):
    """Convert quaternion to rotation matrix."""
    return np.array([
        [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qw*qz), 2*(qx*qz + qw*qy)],
        [2*(qx*qy + qw*qz), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qw*qx)],
        [2*(qx*qz - qw*qy), 2*(qy*qz + qw*qx), 1 - 2*(qx**2 + qy**2)]
    ])


def colmap_to_c2w(qvec, tvec):
    """Convert COLMAP (qvec, tvec) to camera-to-world matrix (OpenGL convention)."""
    R = quat_to_rotation(*qvec)
    t = np.array(tvec)
    w2c = np.eye(4)
    w2c[:3, :3] = R
    w2c[:3, 3] = t
    c2w = np.linalg.inv(w2c)
    c2w[0:3, 1:3] *= -1
    return c2w


class DataPreprocessor:

    def __init__(self, input_dir: str, output_dir: str, model_type: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_type = model_type
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def downsample_images(self, ratio: int = 4) -> Optional[Path]:
        print(f"[*] Downsampling images (1/{ratio})...")
        output_path = self.output_dir / f"images_{ratio}"
        output_path.mkdir(parents=True, exist_ok=True)

        image_exts = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
        images = sorted([f for f in self.input_dir.iterdir() if f.suffix in image_exts])
        if not images:
            print("[!] No image files found")
            return None

        for img_path in images:
            try:
                img = Image.open(img_path)
                w, h = img.size
                new_size = (w // ratio, h // ratio)
                img_resized = img.resize(new_size, Image.LANCZOS)
                img_resized.save(output_path / img_path.name, quality=95)
            except Exception as e:
                print(f"  [!] Failed to process {img_path.name}: {e}")

        print(f"[+] Downsampling complete: {len(images)} images -> {output_path}")
        return output_path

    def run_colmap(self, image_dir: Optional[Path] = None, matcher: str = 'exhaustive') -> Optional[Path]:
        print("[*] Running COLMAP for camera pose estimation...")
        if image_dir is None:
            image_dir = self.input_dir

        colmap_ws = self.output_dir / "colmap_ws"
        if colmap_ws.exists():
            shutil.rmtree(colmap_ws)
        colmap_ws.mkdir(parents=True, exist_ok=True)

        images_link = colmap_ws / "images"
        os.symlink(os.path.abspath(image_dir), images_link)

        (colmap_ws / "sparse").mkdir(parents=True, exist_ok=True)

        matcher_cmd = {
            'exhaustive': 'exhaustive_matcher',
            'sequential': 'sequential_matcher',
            'spatial': 'spatial_matcher',
            'transitive': 'transitive_matcher',
        }.get(matcher, 'exhaustive_matcher')

        db_path = str(colmap_ws / "database.db")
        img_path = str(images_link)
        sparse_path = str(colmap_ws / "sparse")

        # (command template, has_gpu_param) — {gpu} is a placeholder
        steps = [
            (["colmap", "feature_extractor",
              "--database_path", db_path,
              "--image_path", img_path,
              "--ImageReader.single_camera", "1",
              "--SiftExtraction.use_gpu", "{gpu}"], True),
            (["colmap", matcher_cmd,
              "--database_path", db_path,
              "--SiftMatching.use_gpu", "{gpu}"], True),
            (["colmap", "mapper",
              "--database_path", db_path,
              "--image_path", img_path,
              "--output_path", sparse_path], False),
            (["colmap", "image_undistorter",
              "--image_path", img_path,
              "--input_path", str(colmap_ws / "sparse" / "0"),
              "--output_path", str(colmap_ws / "dense"),
              "--output_type", "COLMAP"], False),
        ]

        for cmd_template, has_gpu in steps:
            step = cmd_template[1]
            print(f"  [>] {step}...")

            gpu_options = ["1", "0"] if has_gpu else [None]
            success = False
            for gpu_val in gpu_options:
                if gpu_val is not None:
                    cmd = [c.replace("{gpu}", gpu_val) for c in cmd_template]
                    if gpu_val == "0":
                        print(f"  [!] GPU failed, falling back to CPU...")
                else:
                    cmd = list(cmd_template)

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=28800)
                    if result.returncode == 0:
                        success = True
                        break
                except subprocess.TimeoutExpired:
                    print(f"  [!] {step} timeout (>8 hours)")
                    return None
                except FileNotFoundError:
                    print("  [!] COLMAP not installed or not in PATH")
                    return None

            if not success:
                print(f"  [!] {step} failed")
                if result.stdout.strip():
                    print(f"      stdout: {result.stdout[:500]}")
                if result.stderr.strip():
                    print(f"      stderr: {result.stderr[:500]}")
                return None

        print("[+] COLMAP complete")
        return colmap_ws

    def split_dataset(self, test_ratio: float = 0.1, image_dir: Optional[Path] = None) -> Tuple[Path, Path]:
        print(f"[*] Splitting dataset (test ratio: {test_ratio})...")
        if image_dir is None:
            image_dir = self.input_dir

        images = sorted([f for f in image_dir.iterdir()
                        if f.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
        if not images:
            print("[!] No image files found")
            return None, None

        np.random.seed(42)
        indices = np.random.permutation(len(images))
        test_size = max(1, int(len(images) * test_ratio))

        train_dir = self.output_dir / "train"
        test_dir = self.output_dir / "test"
        train_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

        for idx in indices[test_size:]:
            shutil.copy(images[idx], train_dir / images[idx].name)
        for idx in indices[:test_size]:
            shutil.copy(images[idx], test_dir / images[idx].name)

        print(f"[+] Split complete: train {len(indices)-test_size} images, test {test_size} images")
        return train_dir, test_dir


class NeRFPreprocessor(DataPreprocessor):

    def convert_colmap_to_nerf(self, colmap_dir: Path) -> Optional[Path]:
        """Generate transforms_train.json / transforms_test.json / transforms_val.json.
        file_path has no extension (load_blender.py adds .png automatically).
        Also converts JPG to PNG in train/test directories."""
        print("[*] Converting to NeRF format...")

        sparse_dir = colmap_dir / "sparse" / "0"
        if not sparse_dir.exists():
            print(f"[!] COLMAP sparse directory not found: {sparse_dir}")
            return None

        cameras, images_colmap = read_colmap_binary(sparse_dir)
        if not cameras or not images_colmap:
            print("[!] Failed to read COLMAP model")
            return None

        camera = list(cameras.values())[0]
        fl_x, fl_y, cx, cy = parse_camera_params(camera)

        base_transforms = {
            "camera_angle_x": float(2 * np.arctan(camera['width'] / (2 * fl_x))),
            "camera_angle_y": float(2 * np.arctan(camera['height'] / (2 * fl_y))),
            "fl_x": float(fl_x), "fl_y": float(fl_y),
            "cx": float(cx), "cy": float(cy),
            "w": int(camera['width']), "h": int(camera['height']),
            "aabb_scale": 16,
        }

        train_dir = self.output_dir / "train"
        test_dir = self.output_dir / "test"
        train_stems = {f.stem for f in train_dir.glob('*') if f.suffix.lower() in {'.jpg','.jpeg','.png'}} if train_dir.exists() else set()
        test_stems = {f.stem for f in test_dir.glob('*') if f.suffix.lower() in {'.jpg','.jpeg','.png'}} if test_dir.exists() else set()

        train_frames = []
        test_frames = []
        for _, img_data in images_colmap.items():
            stem = Path(img_data['name']).stem
            c2w = colmap_to_c2w(img_data['qvec'], img_data['tvec'])
            if stem in train_stems:
                train_frames.append({"file_path": f"./train/{stem}", "transform_matrix": c2w.tolist()})
            elif stem in test_stems:
                test_frames.append({"file_path": f"./test/{stem}", "transform_matrix": c2w.tolist()})

        if not test_frames:
            test_frames = train_frames[:max(1, len(train_frames)//10)]

        for name, frames in [("transforms_train.json", train_frames),
                              ("transforms_test.json", test_frames),
                              ("transforms_val.json", test_frames)]:
            out = {**base_transforms, "frames": frames}
            with open(self.output_dir / name, 'w') as f:
                json.dump(out, f, indent=2)

        for d in [train_dir, test_dir]:
            if not d.exists():
                continue
            for jpg in list(d.glob('*.jpg')) + list(d.glob('*.JPG')) + list(d.glob('*.jpeg')):
                png = jpg.with_suffix('.png')
                if not png.exists():
                    Image.open(jpg).save(png)

        print(f"[+] NeRF conversion complete: train={len(train_frames)}, test={len(test_frames)}")
        return self.output_dir / "transforms_train.json"

    def preprocess(self, downsample: int = 4, test_ratio: float = 0.1, matcher: str = 'exhaustive') -> bool:
        print("\n" + "="*60 + "\nNeRF Data Preprocessing\n" + "="*60)

        downsampled_dir = self.downsample_images(downsample)
        if downsampled_dir is None:
            return False

        train_dir, test_dir = self.split_dataset(test_ratio, downsampled_dir)
        if train_dir is None:
            return False

        colmap_dir = self.run_colmap(downsampled_dir, matcher)
        if colmap_dir is None:
            return False

        result = self.convert_colmap_to_nerf(colmap_dir)
        if result is None:
            return False

        print(f"[+] NeRF preprocessing complete! Output: {self.output_dir}")
        return True


class InstantNGPPreprocessor(DataPreprocessor):

    def convert_colmap_to_instant_ngp(self, colmap_dir: Path) -> Optional[Path]:
        """Generate transforms.json with correct c2w matrices."""
        print("[*] Converting to Instant-NGP format...")

        sparse_dir = colmap_dir / "sparse" / "0"
        if not sparse_dir.exists():
            print(f"[!] COLMAP sparse directory not found: {sparse_dir}")
            return None

        cameras, images_colmap = read_colmap_binary(sparse_dir)
        if not cameras or not images_colmap:
            print("[!] Failed to read COLMAP model")
            return None

        camera = list(cameras.values())[0]
        fl_x, fl_y, cx, cy = parse_camera_params(camera)

        train_dir = self.output_dir / "train"
        existing = {f.stem for f in train_dir.glob('*')} if train_dir.exists() else None

        frames = []
        for _, img_data in images_colmap.items():
            stem = Path(img_data['name']).stem
            if existing is not None and stem not in existing:
                continue
            c2w = colmap_to_c2w(img_data['qvec'], img_data['tvec'])
            frames.append({
                "file_path": f"./train/{img_data['name']}",
                "transform_matrix": c2w.tolist()
            })

        transforms = {
            "camera_angle_x": float(2 * np.arctan(camera['width'] / (2 * fl_x))),
            "camera_angle_y": float(2 * np.arctan(camera['height'] / (2 * fl_y))),
            "fl_x": float(fl_x), "fl_y": float(fl_y),
            "cx": float(cx), "cy": float(cy),
            "w": int(camera['width']), "h": int(camera['height']),
            "aabb_scale": 16,
            "frames": frames
        }

        output_file = self.output_dir / "transforms.json"
        with open(output_file, 'w') as f:
            json.dump(transforms, f, indent=2)

        print(f"[+] Instant-NGP conversion complete: {len(frames)} frames -> {output_file}")
        return output_file

    def preprocess(self, downsample: int = 4, test_ratio: float = 0.1, matcher: str = 'exhaustive') -> bool:
        print("\n" + "="*60 + "\nInstant-NGP Data Preprocessing\n" + "="*60)

        downsampled_dir = self.downsample_images(downsample)
        if downsampled_dir is None:
            return False

        train_dir, test_dir = self.split_dataset(test_ratio, downsampled_dir)
        if train_dir is None:
            return False

        colmap_dir = self.run_colmap(downsampled_dir, matcher)
        if colmap_dir is None:
            return False

        result = self.convert_colmap_to_instant_ngp(colmap_dir)
        if result is None:
            return False

        print(f"[+] Instant-NGP preprocessing complete! Output: {self.output_dir}")
        return True


class TwoDGSPreprocessor(DataPreprocessor):
    """2DGS uses standard COLMAP directory structure:
        output/
        ├── images/       (downsampled images)
        └── sparse/
            └── 0/
                ├── cameras.bin
                ├── images.bin
                └── points3D.bin
    """

    def setup_2dgs_structure(self, colmap_dir: Path) -> Optional[Path]:
        """Copy COLMAP sparse results to output directory's sparse/0/."""
        print("[*] Building 2DGS directory structure...")

        sparse_src = colmap_dir / "sparse" / "0"
        if not sparse_src.exists():
            print(f"[!] COLMAP sparse directory not found: {sparse_src}")
            return None

        sparse_dst = self.output_dir / "sparse" / "0"
        if sparse_dst.exists():
            shutil.rmtree(sparse_dst)
        sparse_dst.mkdir(parents=True, exist_ok=True)
        for f in ['cameras.bin', 'images.bin', 'points3D.bin']:
            src = sparse_src / f
            if src.exists():
                shutil.copy2(src, sparse_dst / f)

        print(f"[+] 2DGS structure complete: images/ + sparse/0/")
        return self.output_dir

    def preprocess(self, downsample: int = 4, test_ratio: float = 0.1, matcher: str = 'exhaustive') -> bool:
        print("\n" + "="*60 + "\n2DGS Data Preprocessing\n" + "="*60)

        # 2DGS downsamples directly to images/ directory
        images_dir = self.output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        print(f"[*] Downsampling images (1/{downsample})...")
        image_exts = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
        src_images = sorted([f for f in self.input_dir.iterdir() if f.suffix in image_exts])
        if not src_images:
            print("[!] No image files found")
            return False
        for img_path in src_images:
            try:
                img = Image.open(img_path)
                w, h = img.size
                new_size = (w // downsample, h // downsample)
                img.resize(new_size, Image.LANCZOS).save(images_dir / img_path.name, quality=95)
            except Exception as e:
                print(f"  [!] Failed to process {img_path.name}: {e}")
        print(f"[+] Downsampling complete: {len(src_images)} images -> {images_dir}")

        colmap_dir = self.run_colmap(images_dir, matcher)
        if colmap_dir is None:
            return False

        result = self.setup_2dgs_structure(colmap_dir)
        if result is None:
            return False

        colmap_ws = self.output_dir / "colmap_ws"
        if colmap_ws.exists():
            shutil.rmtree(colmap_ws)

        print(f"[+] 2DGS preprocessing complete! Output: {self.output_dir}")
        return True


def parse_args():
    parser = argparse.ArgumentParser(description='Multi-model neural rendering data preprocessing tool')
    parser.add_argument('--input', '-i', required=True, help='Input image directory')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--model', '-m', required=True,
                       choices=['2dgs', 'instant-ngp', 'nerf'],
                       help='Target model type')
    parser.add_argument('--mode', default='all',
                       choices=['downsample', 'split', 'colmap', 'convert', 'all'],
                       help='Processing mode')
    parser.add_argument('--downsample', '-d', type=int, default=4,
                       help='Downsample factor (1/2/4/8)')
    parser.add_argument('--test_ratio', type=float, default=0.1,
                       help='Test set ratio')
    parser.add_argument('--colmap_matcher', default='exhaustive',
                       choices=['exhaustive', 'sequential', 'spatial', 'transitive'],
                       help='COLMAP matching mode')
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n" + "="*60)
    print("Multi-model Neural Rendering Data Preprocessing Tool")
    print("="*60)
    print(f"Model: {args.model.upper()}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Downsample: 1/{args.downsample}")
    print("="*60 + "\n")

    processors = {
        '2dgs': TwoDGSPreprocessor,
        'instant-ngp': InstantNGPPreprocessor,
        'nerf': NeRFPreprocessor,
    }

    cls = processors.get(args.model)
    if cls is None:
        print(f"[!] Unknown model type: {args.model}")
        return False

    preprocessor = cls(args.input, args.output, args.model)
    success = preprocessor.preprocess(args.downsample, args.test_ratio, args.colmap_matcher)

    if success:
        print(f"\n[+] All processing complete!")
    else:
        print(f"\n[!] Processing failed")
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
