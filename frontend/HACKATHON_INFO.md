# HackHPI 2026: Autonomy in the Fields

## Overview

Welcome to the frontline of agricultural autonomy.

As farming moves toward full autonomy, safety becomes a hard engineering requirement. The goal is not just to build machines, but intelligent systems that can operate in complex, unpredictable environments without putting people at risk.

The challenge, **"Autonomy in the Fields – Life Saving Computer Vision"**, asks teams to act as AI engineers and develop a robust object detection system focused on the most critical asset in the field: human life.

Using real-world agricultural imagery, teams are expected to train and validate Deep Neural Networks (DNNs) that detect and classify people who may be:

- partially hidden by crops
- obscured by dust
- working under low-light conditions

This is a high-stakes safety problem with direct relevance to autonomous harvesting and field operations.

## Timing

- Started: 12 hours ago
- Remaining: 17 hours to go
- Final ranking submission deadline: Saturday at 13:00

## Challenge Description

### Precision Under Pressure

Agricultural environments are difficult for standard computer vision systems. Compared with urban environments, fields introduce strong visual noise and operational uncertainty, including:

- dust
- varying crop heights
- harsh shadows
- changing weather
- partial human visibility

A person may only be partly visible in a field, but an autonomous machine still needs to detect them reliably enough to avoid dangerous behavior.

### Core Task

Participants receive an image dataset captured from agricultural machinery scenes. The goal is to:

1. Invent an approach that prevents hazardous situations in the field.
2. Demonstrate that the approach works with a mockup or a real implementation and proper KPIs.
3. Think beyond the baseline:
   - What is needed to bring the system onto a real agricultural machine?
   - What additional use cases could build on the same approach?

Examples of acceptable technical directions:

- state-of-the-art object detection pipelines such as YOLO
- multimodal approaches such as a VLA

## Data

- Dataset type: images with ground-truth labels in 2D bounding box format
- Annotation format: COCO
- Compute resources: AWS cloud resources (CPU/GPU) are available for training

### Inspecting the Data

Labels can be inspected with tools such as `coco-viewer`.

Example setup on Ubuntu 24:

```bash
pip install opencv-python numpy
git clone https://github.com/PINTO0309/coco-viewer.git
cd coco-viewer
python3 boundingbox_viewer.py \
  -a ${HOME}/HackHPI2026_release/annotation/2023-08-09_A550_autonomyTestRecord_Dissen/aZHUJHxsVAgBoS4a5zQdvl2s-2023-08-09-17-43-23_11_nolabel_coco_jpg.json \
  -i ${HOME}/HackHPI2026_release/data/2023-08-09_A550_autonomyTestRecord_Dissen/2023-08-09-17-43-23
```

## Submission Requirements

A valid submission must be summarized in a **Kaggle Writeup** and include:

- Media Gallery
- Code
- Presentation
- Evaluation

The final submission must be submitted before the deadline. Draft or unsubmitted writeups at the deadline will not be considered.

To create a submission:

1. Click `New Writeup`.
2. Save the writeup.
3. Use the `Submit` button in the top right.

### Important Kaggle Note

If a private Kaggle Resource is attached to a public Kaggle Writeup, that private resource will automatically become public after the deadline.

## Preliminaries and Constraints

The dataset and models are subject to strict handling constraints:

- The provided dataset may only be processed locally or on AWS-hosted infrastructure during the competition.
- Do not upload videos from the dataset to public platforms such as YouTube.
- Do not upload pictures from the dataset to third-party web services.
- All models must run locally or on AWS-hosted infrastructure.
- The use of online AI services for model execution is prohibited, including services such as `gemini.google.com`.

This prohibition applies to:

- DNNs
- VLAs
- LLMs
- any other multimodal model hosted as an online service

## Kaggle Writeup Details

The Kaggle Writeup serves as the project report. It should include a title, subtitle, and a detailed analysis of the submission.

There is no explicit word limit.

To be eligible, the following assets must be attached:

### 1. Media Gallery

- Attach relevant images for the submission.
- A cover image is required.
- No dataset image may be uploaded at a resolution higher than `320x240`.

### 2. Code

- The code must be publicly available, for example via GitHub.

### 3. Presentation

- Attach the final presentation as a PDF.

### 4. Evaluation

- The team must challenge and evaluate its own solution.
- Quantitative evaluation is preferred.
- Qualitative evaluation is also acceptable, for example user or customer feedback if relevant.

## Submission Deadline

- Teams may submit results via the Kaggle platform.
- The final ranking submission must be selected before the deadline on Saturday at 13:00.

## Evaluation Criteria

The final hackathon score is split into two parts.

### 1. Quantitative Evaluation

Domain experts will judge the technical performance and effectiveness of the solution.

### 2. Qualitative Evaluation

Each team must deliver a final pitch to the jury. The pitch will be judged on:

- **Technical Approach**
  - quality of the chosen approach
  - treatment of agricultural edge cases
- **Innovation and Future Vision**
  - feasibility on edge hardware for a real harvester
  - handling false positives such as scarecrows or fence posts
  - expansion into further business cases or additional protected-object categories
- **Clarity of Presentation**
  - how clearly the team communicates findings and engineering decisions

## Tracks and Awards

- Event: HackHPI 2026
- Prize details: announced during the hackathon
- Track awards: TBA

## Judges

- Timo Korthals, Data Scientist, CLAAS E-Systems GmbH
- Jannik Redenius, Project Manager, CLAAS E-Systems GmbH

## Practical Checklist

Use this as a final submission checklist:

- Build an approach that addresses hazardous field situations
- Show evidence that it works with KPIs
- Prepare a Kaggle Writeup
- Add a cover image
- Add code repository link
- Attach final presentation PDF
- Add quantitative and/or qualitative evaluation
- Confirm all assets comply with dataset-sharing restrictions
- Submit before Saturday at 13:00
