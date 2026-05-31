from ultralytics import YOLO

def train():
    # Load a pretrained model (recommended for training)
    model = YOLO('yolov8n.pt') 

    # Train the model
    # You need to provide a data.yaml file that points to your annotated dataset.
    # The dataset should have annotations in YOLO format (txt files).
    print("Starting training...")
    results = model.train(
        data='data.yaml', 
        epochs=100, 
        imgsz=640,
        name='cad_balloon_detector',
        device='cpu' # Change to 0 if you have a GPU
    )

    print("Training complete. Your best model will be saved in runs/detect/cad_balloon_detector/weights/best.pt")
    print("Please copy best.pt to processing-service/balloon_detector.pt for inference.")

if __name__ == '__main__':
    train()
