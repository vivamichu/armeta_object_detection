import cv2
import numpy as np
import os
import random
from pathlib import Path
import shutil

def load_qr_codes(qr_folder):
    """Load all QR codes from the chosen_qr folder"""
    qr_codes = []
    qr_folder_path = Path(qr_folder)
    
    for qr_file in qr_folder_path.glob('*.jpg'):
        qr_img = cv2.imread(str(qr_file), cv2.IMREAD_UNCHANGED)
        if qr_img is not None:
            qr_codes.append((qr_img, qr_file.name))
            print(f"Loaded QR code: {qr_file.name}, size: {qr_img.shape}")
    
    print(f"Total QR codes loaded: {len(qr_codes)}")
    return qr_codes

def resize_qr_code(qr_img, target_size):
    """Resize QR code to target size while maintaining aspect ratio"""
    h, w = qr_img.shape[:2]
    
    # Calculate scale to fit within target size
    scale = min(target_size[0] / w, target_size[1] / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    resized_qr = cv2.resize(qr_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized_qr

def paste_qr_on_image(image, qr_img, position, alpha=1.0):
    """Paste QR code on image at specified position"""
    qr_h, qr_w = qr_img.shape[:2]
    img_h, img_w = image.shape[:2]
    
    # Ensure position is within bounds
    x, y = position
    if x + qr_w > img_w or y + qr_h > img_h or x < 0 or y < 0:
        return None
    
    # Paste QR code
    if len(qr_img.shape) == 3 and qr_img.shape[2] == 4:  # RGBA
        # Handle transparency
        qr_rgb = qr_img[:, :, :3]
        qr_alpha = qr_img[:, :, 3] / 255.0
        
        for c in range(3):
            image[y:y+qr_h, x:x+qr_w, c] = (
                qr_alpha * qr_rgb[:, :, c] + 
                (1 - qr_alpha) * image[y:y+qr_h, x:x+qr_w, c]
            )
    else:
        # Simple paste for RGB/Grayscale
        if len(qr_img.shape) == 2:  # Grayscale QR
            qr_img = cv2.cvtColor(qr_img, cv2.COLOR_GRAY2BGR)
        
        image[y:y+qr_h, x:x+qr_w] = cv2.addWeighted(
            image[y:y+qr_h, x:x+qr_w], 1-alpha, qr_img, alpha, 0
        )
    
    return (x, y, qr_w, qr_h)

def get_qr_positions(img_shape, qr_size, num_qrs=1):
    """Generate positions for QR codes (corners + random)"""
    img_h, img_w = img_shape[:2]
    qr_h, qr_w = qr_size
    
    positions = []
    
    # Define corner positions with some margin
    margin = 10
    corners = [
        (margin, margin),  # Top-left
        (img_w - qr_w - margin, margin),  # Top-right
        (margin, img_h - qr_h - margin),  # Bottom-left
        (img_w - qr_w - margin, img_h - qr_h - margin)  # Bottom-right
    ]
    
    # Add corner positions first
    available_corners = corners.copy()
    corner_count = min(num_qrs, len(available_corners))
    
    for i in range(corner_count):
        if available_corners:
            pos = available_corners.pop(random.randint(0, len(available_corners)-1))
            positions.append(pos)
    
    # Add random positions for remaining QRs
    remaining_qrs = num_qrs - corner_count
    max_attempts = 50
    
    for _ in range(remaining_qrs):
        attempts = 0
        while attempts < max_attempts:
            x = random.randint(margin, max(margin, img_w - qr_w - margin))
            y = random.randint(margin, max(margin, img_h - qr_h - margin))
            
            # Check if position doesn't overlap with existing positions
            new_pos = (x, y)
            overlap = False
            
            for existing_pos in positions:
                ex, ey = existing_pos
                if (abs(x - ex) < qr_w and abs(y - ey) < qr_h):
                    overlap = True
                    break
            
            if not overlap:
                positions.append(new_pos)
                break
            
            attempts += 1
    
    return positions

def get_qr_positions_mixed(img_shape, qr_size, num_qrs=1, corner_prob=0.5, margin=10):
    """Generate up to num_qrs positions blending corners and random placements.
    Ensures no overlap between generated QR placements.
    corner_prob controls the probability a placement will use a corner.
    """
    img_h, img_w = img_shape[:2]
    qr_h, qr_w = qr_size

    positions = []
    corners = [
        (margin, margin),
        (img_w - qr_w - margin, margin),
        (margin, img_h - qr_h - margin),
        (img_w - qr_w - margin, img_h - qr_h - margin)
    ]
    available_corners = corners.copy()
    max_attempts = 100

    for _ in range(num_qrs):
        use_corner = random.random() < corner_prob and len(available_corners) > 0
        if use_corner:
            pos = available_corners.pop(random.randint(0, len(available_corners) - 1))
            # Avoid overlap with already chosen positions (rare for corners, but check)
            overlap = any(abs(pos[0]-ex) < qr_w and abs(pos[1]-ey) < qr_h for ex, ey in positions)
            if not overlap:
                positions.append(pos)
                continue
            # If overlap for some reason, fall back to random
        # Random placement with overlap avoidance
        attempts = 0
        placed = False
        while attempts < max_attempts and not placed:
            x = random.randint(margin, max(margin, img_w - qr_w - margin))
            y = random.randint(margin, max(margin, img_h - qr_h - margin))
            overlap = any(abs(x-ex) < qr_w and abs(y-ey) < qr_h for ex, ey in positions)
            if not overlap:
                positions.append((x, y))
                placed = True
                break
            attempts += 1
        if not placed and available_corners:  # last resort: try any remaining corner
            pos = available_corners.pop(0)
            positions.append(pos)

    return positions

def convert_to_yolo_format(bbox, img_shape):
    """Convert bounding box to YOLO format (normalized)"""
    x, y, w, h = bbox
    img_h, img_w = img_shape[:2]
    
    # Calculate center coordinates and normalize
    center_x = (x + w/2) / img_w
    center_y = (y + h/2) / img_h
    norm_w = w / img_w
    norm_h = h / img_h
    
    return center_x, center_y, norm_w, norm_h

def load_existing_annotations(label_path):
    """Load existing YOLO format annotations"""
    annotations = []
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    annotations.append(line)
    return annotations

def save_annotations(label_path, annotations):
    """Save YOLO format annotations"""
    os.makedirs(os.path.dirname(label_path), exist_ok=True)
    with open(label_path, 'w') as f:
        for annotation in annotations:
            f.write(f"{annotation}\n")

def process_dataset_split(dataset_path, split_name, qr_codes, num_images_to_modify,
                          size_frac_range=(0.08, 0.18), qrs_per_image_range=(1, 3), corner_prob=0.5):
    """Process a dataset split (train/valid) and add QR codes to a subset of images.
    - num_images_to_modify: number of images in this split that will receive QR codes
    - size_frac_range: (min,max) fraction of min(image dimension) for QR size
    - qrs_per_image_range: (min,max) number of QRs to paste per selected image
    - corner_prob: probability of placing a QR in a corner vs a random spot
    """
    images_dir = os.path.join(dataset_path, split_name, 'images')
    labels_dir = os.path.join(dataset_path, split_name, 'labels')
    
    # Create output directories
    output_images_dir = os.path.join(dataset_path, f'{split_name}_with_qr', 'images')
    output_labels_dir = os.path.join(dataset_path, f'{split_name}_with_qr', 'labels')
    os.makedirs(output_images_dir, exist_ok=True)
    os.makedirs(output_labels_dir, exist_ok=True)
    
    # Get all image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(Path(images_dir).glob(ext))
    image_files = list(image_files)

    print(f"\nProcessing {split_name} split: {len(image_files)} images")

    # Determine which images to modify
    random.shuffle(image_files)
    num_images_to_modify = min(num_images_to_modify, len(image_files))
    selected_images = set(image_files[:num_images_to_modify])
    print(f"Will paste QR codes into {len(selected_images)} {split_name} images")

    total_qr_added = 0
    modified_images_count = 0

    for i, img_path in enumerate(image_files):
        # Load image
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"Could not load image: {img_path}")
            continue

        # Prepare paths
        output_img_path = os.path.join(output_images_dir, img_path.name)
        label_path = os.path.join(labels_dir, img_path.stem + '.txt')
        output_label_path = os.path.join(output_labels_dir, img_path.stem + '.txt')

        # Load existing annotations
        annotations = load_existing_annotations(label_path)

        if img_path in selected_images:
            # Decide how many QRs to place on this image
            min_qr, max_qr = qrs_per_image_range
            if max_qr < min_qr:
                max_qr = min_qr
            num_qrs_this_image = random.randint(min_qr, max_qr)

            # Determine QR size relative to image
            img_h, img_w = image.shape[:2]
            min_dim = max(1, min(img_h, img_w))

            # For each QR, choose size and position
            # To reduce overlap, precompute positions with a single size per image
            size_frac = random.uniform(size_frac_range[0], size_frac_range[1])
            qr_size_px = max(8, int(round(min_dim * size_frac)))

            positions = get_qr_positions_mixed(
                image.shape, (qr_size_px, qr_size_px), num_qrs_this_image, corner_prob=corner_prob, margin=10
            )

            for pos in positions:
                qr_img, qr_name = random.choice(qr_codes)
                resized_qr = resize_qr_code(qr_img, (qr_size_px, qr_size_px))
                bbox = paste_qr_on_image(image, resized_qr, pos, alpha=0.9)
                if bbox:
                    yolo_bbox = convert_to_yolo_format(bbox, image.shape)
                    qr_class = 0  # 'qr' is class 0 according to data.yaml
                    annotation = f"{qr_class} {yolo_bbox[0]:.6f} {yolo_bbox[1]:.6f} {yolo_bbox[2]:.6f} {yolo_bbox[3]:.6f}"
                    annotations.append(annotation)
                    total_qr_added += 1
            modified_images_count += 1
            # Save modified image
            cv2.imwrite(output_img_path, image)
            save_annotations(output_label_path, annotations)
            print(f"Modified [{modified_images_count}/{len(selected_images)}] {img_path.name} with {len(positions)} QR(s)")
        else:
            # Copy original files untouched
            shutil.copy2(str(img_path), output_img_path)
            if os.path.exists(label_path):
                shutil.copy2(label_path, output_label_path)

    print(f"Completed {split_name} split: Modified {modified_images_count} images, Added {total_qr_added} QR codes")
    return modified_images_count, total_qr_added

def main():
    # Paths
    qr_folder = "/home/sara_team/Desktop/case/chosen_qr"
    dataset_path = "/home/sara_team/Desktop/case/IDP_stamp_signature_detection.v4i.yolov11"
    
    # Parameters: number of images to modify per split
    train_images_with_qr = 300
    valid_images_with_qr = 100

    # Reasonable relative QR size and count per image
    size_frac_range = (0.08, 0.18)  # 8% to 18% of min(image dimension)
    qrs_per_image_range = (1, 3)    # paste between 1 and 3 per selected image
    corner_prob = 0.5               # mix corners and random placements
    
    print("Loading QR codes...")
    qr_codes = load_qr_codes(qr_folder)
    
    if not qr_codes:
        print("No QR codes found! Please check the path.")
        return
    
    print(f"Found {len(qr_codes)} QR codes. Will use duplicates as needed.")
    
    # Process train split
    train_modified, train_qr_added = process_dataset_split(
        dataset_path, 'train', qr_codes, train_images_with_qr,
        size_frac_range=size_frac_range,
        qrs_per_image_range=qrs_per_image_range,
        corner_prob=corner_prob
    )
    
    # Process validation split
    valid_modified, valid_qr_added = process_dataset_split(
        dataset_path, 'valid', qr_codes, valid_images_with_qr,
        size_frac_range=size_frac_range,
        qrs_per_image_range=qrs_per_image_range,
        corner_prob=corner_prob
    )
    
    print(f"\n=== Summary ===")
    print(f"{train_modified} train images modified, total QR pasted: {train_qr_added}")
    print(f"{valid_modified} valid images modified, total QR pasted: {valid_qr_added}")
    print(f"Output directories:")
    print(f"  - {dataset_path}/train_with_qr/")
    print(f"  - {dataset_path}/valid_with_qr/")

if __name__ == "__main__":
    main()