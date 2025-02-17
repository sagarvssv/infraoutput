from flask import Flask, jsonify
import platform
import psutil
import socket
import pymongo

app = Flask(__name__)

# MongoDB connection
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["infraoutput"]
collection = db["system_info"]

def get_system_info():
    system_info = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "cpu": platform.processor(),
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "memory_total": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "disk_total": round(psutil.disk_usage('/').total / (1024 ** 3), 2)
    }
    return system_info

@app.route('/')
def home():
    return "Hello, Flask is running in Docker!"

@app.route('/scan', methods=['GET'])
def scan_system():
    system_info = get_system_info()
    collection.insert_one(system_info)
    return jsonify({"status": "success", "data": system_info})

@app.route('/fetch', methods=['GET'])
def fetch_data():
    data = list(collection.find({}, {"_id": 0}))
    return jsonify({"status": "success", "data": data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
