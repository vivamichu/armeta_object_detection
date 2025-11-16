from roboflow import Roboflow
import os
from pathlib import Path

# Initialize the Roboflow object with your API key
rf = Roboflow(api_key="key")

# Retrieve your current workspace and project name
print(rf.workspace())

# https://app.roboflow.com/trains-zl4qq/idp_stamp_signature_detection-x7dou-gqehd
# Specify the project for upload
workspaceId = 'id'
projectId = 'id'
project = rf.workspace(workspaceId).project(projectId)

# Define the path to archive folder
archive_path = "path"

# Get all image files in the archive folder
image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
image_files = []

for file in os.listdir(archive_path):
    file_lower = file.lower()
    if any(file_lower.endswith(ext) for ext in image_extensions):
        image_files.append(file)

print(f"Found {len(image_files)} images to upload from archive folder...")

# Upload images with batch processing
batch_size = 50  # Upload in batches to avoid overwhelming the API
total_files = len(image_files)

for i in range(0, total_files, batch_size):
    batch_files = image_files[i:i+batch_size]
    batch_num = (i // batch_size) + 1
    
    print(f"\nUploading batch {batch_num} ({len(batch_files)} images)...")
    
    for j, image_file in enumerate(batch_files):
        image_path = os.path.join(archive_path, image_file)
        file_index = i + j + 1
        
        try:
            # Upload each image with appropriate metadata
            project.upload(
                image_path=image_path,
                batch_name=f"archive_documents_batch_{batch_num}",
                split="train",  # You can change this to "valid" or "test" as needed
                num_retry_uploads=3,
                tag_names=["archive", "documents", f"batch_{batch_num}"],
                sequence_number=file_index,
                sequence_size=total_files
            )
            print(f"✓ Uploaded {image_file} ({file_index}/{total_files})")
            
        except Exception as e:
            print(f"✗ Error uploading {image_file}: {str(e)}")
            continue

print(f"\nUpload completed! Processed {total_files} images from archive folder.")
