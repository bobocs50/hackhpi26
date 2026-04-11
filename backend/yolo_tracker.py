import csv
from collections import defaultdict
from pathlib import Path

import cv2
import torch
from torch.nn.functional import cosine_similarity
from torchvision import transforms
from torchvision.models import ResNet50_Weights, resnet50
from ultralytics import YOLO


MODEL_YOLO = "yolo26m.pt"
SIMILARITY_THRESHOLD = 0.75
FRAME_LIMIT = 20


def run_yolo_tracker(image_folder: str | Path, output_folder: str | Path) -> dict[str, str | int]:
    image_folder = Path(image_folder)
    output_folder = Path(output_folder)

    # -----------------------------------------
    # 1. Configuration & Setup
    # -----------------------------------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_folder.mkdir(parents=True, exist_ok=True)

    print(f"Loading models on {device}...")
    yolo_model = YOLO(MODEL_YOLO).to(device)
    class_names = yolo_model.names

    resnet = resnet50(weights=ResNet50_Weights.DEFAULT).to(device)
    embedder = torch.nn.Sequential(*(list(resnet.children())[:-1]))
    embedder.to(device)
    embedder.eval()

    preprocess = transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    # -----------------------------------------
    # 2. Tracking Memory
    # -----------------------------------------
    known_features = defaultdict(list)
    known_ids = defaultdict(list)
    next_id = 1

    csv_path = output_folder / f"multiclass_tracking_{FRAME_LIMIT}frames.csv"
    csv_headers = [
        "frame_idx",
        "class_name",
        "track_id",
        "foot_x",
        "foot_y",
        "bbox_x1",
        "bbox_y1",
        "bbox_x2",
        "bbox_y2",
    ]

    # -----------------------------------------
    # 3. Processing Core
    # -----------------------------------------
    image_paths = sorted(
        [
            image_path
            for image_path in image_folder.iterdir()
            if image_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        ]
    )[:FRAME_LIMIT]

    if not image_paths:
        raise ValueError(f"No supported image files found in {image_folder}")

    print(f"Starting processing for {len(image_paths)} frames...")

    with csv_path.open("w", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(csv_headers)

        for idx, img_path in enumerate(image_paths):
            frame = cv2.imread(str(img_path))
            if frame is None:
                continue

            annotated_frame = frame.copy()
            results = yolo_model(frame, imgsz=1280, verbose=False)[0]

            for box in results.boxes:
                if float(box.conf) < 0.25:
                    continue

                cls_idx = int(box.cls)
                cls_name = class_names[cls_idx]
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                crop = frame[max(0, y1) : min(frame.shape[0], y2), max(0, x1) : min(frame.shape[1], x2)]
                if crop.size == 0 or crop.shape[0] < 5 or crop.shape[1] < 5:
                    continue

                img_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                input_tensor = preprocess(img_rgb).unsqueeze(0).to(device)

                with torch.no_grad():
                    embedding = embedder(input_tensor).squeeze()

                final_id = None
                max_sim_value = None

                if known_features[cls_idx]:
                    sims = cosine_similarity(
                        embedding.unsqueeze(0),
                        torch.stack(known_features[cls_idx]),
                    )
                    max_sim, max_idx = torch.max(sims, dim=0)

                    if max_sim.item() > SIMILARITY_THRESHOLD:
                        final_id = known_ids[cls_idx][max_idx.item()]
                        max_sim_value = float(max_sim.item())

                if final_id is None:
                    final_id = next_id
                    known_features[cls_idx].append(embedding.detach())
                    known_ids[cls_idx].append(final_id)
                    next_id += 1

                foot_x = int((x1 + x2) / 2)
                foot_y = y2
                writer.writerow([idx, cls_name, final_id, foot_x, foot_y, x1, y1, x2, y2])

                label = f"{cls_name} #{final_id}"
                if max_sim_value is not None:
                    label = f"{label} ({max_sim_value:.2f})"

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_frame,
                    label,
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

            save_path = output_folder / f"frame_{idx:03d}_reid.jpg"
            cv2.imwrite(str(save_path), annotated_frame)
            print(f"Done frame {idx + 1}/{len(image_paths)}")
            print(f"Processed: {save_path}")

    print("Video Processing Done!")
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
