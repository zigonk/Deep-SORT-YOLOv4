#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, absolute_import

from timeit import time
import warnings
import cv2
import numpy as np
from PIL import Image

from deep_sort import preprocessing
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.detection_yolo import Detection_YOLO
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet
import imutils.video
from videocaptureasync import VideoCaptureAsync
import json

import argparse

warnings.filterwarnings('ignore')

def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('input', type=str, help='Input video path')
    parser.add_argument('bbox', type=str, help='Input bounding box path')
    parser.add_argument('output', type=str, help='Ouput video path')
    args = parser.parse_args()

    # Definition of the parameters
    max_cosine_distance = 0.3
    nn_budget = None
    nms_max_overlap = 1.0
    
    # Deep SORT
    model_filename = 'model_data/mars-small128.pb'
    encoder = gdet.create_box_encoder(model_filename, batch_size=1)
    
    metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
    tracker = Tracker(metric)

    tracking = True
    writeVideo_flag = True
    asyncVideo_flag = False

    file_path = args.input
    if asyncVideo_flag :
        video_capture = VideoCaptureAsync(file_path)
    else:
        video_capture = cv2.VideoCapture(file_path)

    if asyncVideo_flag:
        video_capture.start()

    if writeVideo_flag:
        if asyncVideo_flag:
            w = int(video_capture.cap.get(3))
            h = int(video_capture.cap.get(4))
        else:
            w = int(video_capture.get(3))
            h = int(video_capture.get(4))
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(args.output, fourcc, 30, (w, h))
        frame_index = -1

    fps = 0.0
    # fps_imutils = imutils.video.FPS().start()

    with open(args.bbox) as f:
        data = json.load(f)
    frame_index = 0
    while True:
        ret, frame = video_capture.read()  # frame shape 640*480*3
        if ret != True:
             break

        t1 = time.time()

        image = Image.fromarray(frame[...,::-1])  # bgr to rgb
        boxes = np.asarray([pred['bbox'] for pred in data[frame_index]['annotations']])
        confidence = np.asarray([pred['score'] for pred in data[frame_index]['annotations']])
        classes = np.asarray([pred['label'] for pred in data[frame_index]['annotations']])

        if tracking:
            features = encoder(frame, boxes)

            detections = [Detection(bbox, confidence, cls, feature) for bbox, confidence, cls, feature in
                          zip(boxes, confidence, classes, features)]

        # Run non-maxima suppression.
        boxes = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        indices = preprocessing.non_max_suppression(boxes, nms_max_overlap, scores)
        detections = [detections[i] for i in indices]

        if tracking:
            # Call the tracker
            tracker.predict()
            tracker.update(detections)

            for track in tracker.tracks:
                if not track.is_confirmed() or track.time_since_update > 1:
                    continue
                bbox = track.to_tlbr()
                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 255, 255), 2)
                cv2.putText(frame, "ID: " + str(track.track_id), (int(bbox[0]), int(bbox[1])), 0,
                            1.5e-3 * frame.shape[0], (0, 255, 0), 1)

        for det in detections:
            bbox = det.to_tlbr()
            score = "%.2f" % round(det.confidence * 100, 2) + "%"
            cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 0, 0), 2)
            if len(classes) > 0:
                cls = det.cls
                cv2.putText(frame, str(cls) + " " + score, (int(bbox[0]), int(bbox[3])), 0,
                            1.5e-3 * frame.shape[0], (0, 255, 0), 1)

        # cv2.imshow('', frame)

        if writeVideo_flag: # and not asyncVideo_flag:
            # save a frame
            out.write(frame)
            frame_index = frame_index + 1

        # fps_imutils.update()

        # if not asyncVideo_flag:
        #     fps = (fps + (1./(time.time()-t1))) / 2
        #     print("FPS = %f"%(fps))
        
        # Press Q to stop!
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #     break

    # fps_imutils.stop()
    # print('imutils FPS: {}'.format(fps_imutils.fps()))

    if asyncVideo_flag:
        video_capture.stop()
    else:
        video_capture.release()

    if writeVideo_flag:
        out.release()

    # cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
