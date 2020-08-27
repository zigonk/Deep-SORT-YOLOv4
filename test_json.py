import json

with open('cam_01.json') as f:
    data = json.load(f)

print(data[0]['annotations'])