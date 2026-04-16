# from fastapi import FastAPI, UploadFile
# from ultralytics import YOLO
# import numpy as np
# import cv2
# import base64

# app = FastAPI()

# # load model
# model = YOLO("yolov8n.pt")


# @app.get("/")
# def home():
#     return {"msg": "Server OK"}

# @app.post("/detect")
# async def detect(file: UploadFile):
#     try:
#         contents = await file.read()

#         nparr = np.frombuffer(contents, np.uint8)
#         img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#         print("IMG OK:", img is not None)

#         if img is None:
#             return {"error": "Decode ảnh lỗi"}

#         results = model(img)

#         print("RESULT:", results)

#         detections = []

#         for r in results:
#             if r.boxes is None:
#                 continue

#             for box in r.boxes:
#                 detections.append({
#                     "class": int(box.cls[0]),
#                     "confidence": float(box.conf[0]),
#                     "xyxy": box.xyxy[0].tolist()
#                 })

#         annotated = results[0].plot()

#         _, buffer = cv2.imencode('.jpg', annotated)

#         return {
#             "detections": detections,
#             "image": base64.b64encode(buffer).decode()
#         }

#     except Exception as e:
#         print("🔥 ERROR:", e)
#         return {"error": str(e)}