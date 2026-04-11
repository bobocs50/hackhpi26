import csv
from collections import defaultdict
from pathlib import Path

import cv2
import torch
from scipy.spatial.distance import cosine
from torchvision import transforms
from torchvision.models import ResNet50_Weights, resnet50
from ultralytics import YOLO


def run_yolo_tracker(image_folder: str | Path, output_folder: str | Path) -> dict[str, str | int]:
    image_folder = Path(image_folder)
    output_folder = Path(output_folder)

    # -----------------------------------------
    # 1. Initialization
    # -----------------------------------------
    print("Loading Models...")
    yolo_model = YOLO("yolo26m.pt")

    resnet = resnet50(weights=ResNet50_Weights.DEFAULT)
    embedder = torch.nn.Sequential(*(list(resnet.children())[:-1]))
    embedder.eval()

    # Transformation to prepare the cropped image for ResNet
    preprocess = transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    # -----------------------------------------
    # 2. Data & Export Setup
    # -----------------------------------------
    image_paths = sorted(
        [
            image_path
            for image_path in image_folder.iterdir()
            if image_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        ]
    )[:20]

    if not image_paths:
        raise ValueError(f"No supported image files found in {image_folder}")

    output_folder.mkdir(parents=True, exist_ok=True)
    csv_path = output_folder / "trajectory_data.csv"

    # -----------------------------------------
    # 3. Tracking Memory & Data Storage
    # -----------------------------------------
    known_people_fingerprints = []  # Store dictionaries: {"id": 1, "embedding": [...]}
    next_id = 1

    # Data structures for exporting
    track_history = defaultdict(list)  # Stores (X, Y) foot coordinates to draw the trail
    csv_data = [
        [
            "frame_idx",
            "track_id",
            "foot_x",
            "foot_y",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
            "similarity_score",
        ]
    ]

    # -----------------------------------------
    # 4. Processing Loop
    # -----------------------------------------
    for idx, img_path in enumerate(image_paths):
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        annotated_frame = frame.copy()

        # A. Detect with YOLO
        results = yolo_model(frame, imgsz=1280)[0]

        for box in results.boxes:
            if int(box.cls) == 0 and float(box.conf) > 0.2:  # It's a person
                # B. Get Coordinates and Crop
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Calculate "Feet" Coordinates (Bottom center of the bounding box)
                foot_x = int((x1 + x2) / 2)
                foot_y = int(y2)

                # Boundary check
                cy1, cy2 = max(0, y1), min(frame.shape[0], y2)
                cx1, cx2 = max(0, x1), min(frame.shape[1], x2)

                person_crop = frame[cy1:cy2, cx1:cx2]

                if person_crop.shape[0] < 10 or person_crop.shape[1] < 10:
                    continue

                # C. Generate the Fingerprint (Embedding)
                person_rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
                input_tensor = preprocess(person_rgb).unsqueeze(0)

                with torch.no_grad():
                    embedding = embedder(input_tensor).numpy().flatten()

                # D. Compare against known fingerprints
                best_match_id = None
                highest_similarity = 0.0

                for known_person in known_people_fingerprints:
                    similarity = 1 - cosine(embedding, known_person["embedding"])

                    if similarity > 0.75:
                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_match_id = known_person["id"]

                # E. Assign ID
                if best_match_id is not None:
                    final_id = best_match_id
                else:
                    final_id = next_id
                    known_people_fingerprints.append({"id": final_id, "embedding": embedding})
                    next_id += 1

                # --- F. Store Data and Draw ---
                display_sim = highest_similarity if best_match_id else 1.0

                # Save for CSV and Plotting
                track_history[final_id].append((foot_x, foot_y))
                csv_data.append([idx, final_id, foot_x, foot_y, x1, y1, x2, y2, round(display_sim, 3)])

                # Draw Bounding Box and ID
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_frame,
                    f"ID: {final_id} ({display_sim:.2f})",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

                # Draw the Trajectory Line behind them on the image
                points = track_history[final_id]
                for point_index in range(1, len(points)):
                    cv2.line(annotated_frame, points[point_index - 1], points[point_index], (255, 0, 0), 3)

        # Save visual result
        save_path = output_folder / f"frame_{idx:03d}_reid.jpg"
        cv2.imwrite(str(save_path), annotated_frame)
        print(f"Processed: {save_path}")

    print("Video Processing Done!")

    # -----------------------------------------
    # 5. Exporting CSV
    # -----------------------------------------
    print("Exporting Data...")

    # Write to CSV
    with csv_path.open("w", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerows(csv_data)
    print(f"-> Saved coordinates to: {csv_path}")
    print("All tasks completed.")

    return {
        "processed_frames": len(image_paths),
        "csv_path": str(csv_path),
    }


if __name__ == "__main__":
    run_yolo_tracker(
        Path(__file__).resolve().parent / "2023-09-07-16-24-19",
        Path(__file__).resolve().parent / "yolo_resnet_final",
    )
