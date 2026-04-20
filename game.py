import os
import json
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
DATA_FILE = os.path.join(DATA_DIR, "rebuses.json")


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return send_from_directory("static", "menu.html")


@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(load_data())


@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
