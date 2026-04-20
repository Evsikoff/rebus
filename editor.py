import os
import json
import uuid
import io
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file
from PIL import Image

app = Flask(__name__, static_folder="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
DATA_FILE = os.path.join(DATA_DIR, "rebuses.json")
IMAGE_SIZE = (200, 200)

os.makedirs(IMAGES_DIR, exist_ok=True)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def process_image(image_bytes):
    """Resize image to 200x200 and save as PNG. Returns filename."""
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGBA")
    img = img.resize(IMAGE_SIZE, Image.LANCZOS)
    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(IMAGES_DIR, filename)
    img.save(filepath, "PNG")
    return filename


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(load_data())


@app.route("/api/data", methods=["PUT"])
def update_data():
    data = request.get_json()
    save_data(data)
    return jsonify({"ok": True})


@app.route("/api/levels", methods=["POST"])
def add_level():
    data = load_data()
    body = request.get_json()
    new_id = max((l["id"] for l in data["levels"]), default=0) + 1
    data["levels"].append({
        "id": new_id,
        "name": body.get("name", f"Уровень {new_id}"),
        "rebuses": []
    })
    save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:level_id>", methods=["DELETE"])
def delete_level(level_id):
    data = load_data()
    level = next((l for l in data["levels"] if l["id"] == level_id), None)
    if level:
        for rebus in level["rebuses"]:
            for img in rebus.get("images", []):
                path = os.path.join(IMAGES_DIR, img)
                if os.path.exists(path):
                    os.remove(path)
        data["levels"] = [l for l in data["levels"] if l["id"] != level_id]
        save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:level_id>/name", methods=["PUT"])
def rename_level(level_id):
    data = load_data()
    body = request.get_json()
    for level in data["levels"]:
        if level["id"] == level_id:
            level["name"] = body["name"]
            break
    save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:level_id>/rebuses", methods=["POST"])
def add_rebus(level_id):
    data = load_data()
    body = request.get_json()
    for level in data["levels"]:
        if level["id"] == level_id:
            rebus_id = uuid.uuid4().hex[:8]
            level["rebuses"].append({
                "id": rebus_id,
                "answer": body.get("answer", ""),
                "images": [],
                "order": len(level["rebuses"])
            })
            save_data(data)
            return jsonify(data)
    return jsonify({"error": "Level not found"}), 404


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>", methods=["PUT"])
def update_rebus(level_id, rebus_id):
    data = load_data()
    body = request.get_json()
    for level in data["levels"]:
        if level["id"] == level_id:
            for rebus in level["rebuses"]:
                if rebus["id"] == rebus_id:
                    if "answer" in body:
                        rebus["answer"] = body["answer"]
                    if "order" in body:
                        rebus["order"] = body["order"]
                    save_data(data)
                    return jsonify(data)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>", methods=["DELETE"])
def delete_rebus(level_id, rebus_id):
    data = load_data()
    for level in data["levels"]:
        if level["id"] == level_id:
            rebus = next((r for r in level["rebuses"] if r["id"] == rebus_id), None)
            if rebus:
                for img in rebus.get("images", []):
                    path = os.path.join(IMAGES_DIR, img)
                    if os.path.exists(path):
                        os.remove(path)
                level["rebuses"] = [r for r in level["rebuses"] if r["id"] != rebus_id]
                for i, r in enumerate(level["rebuses"]):
                    r["order"] = i
                save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>/upload", methods=["POST"])
def upload_image(level_id, rebus_id):
    data = load_data()
    files = request.files.getlist("image")
    if not files:
        return jsonify({"error": "No images provided"}), 400

    filenames = [process_image(f.read()) for f in files]

    for level in data["levels"]:
        if level["id"] == level_id:
            for rebus in level["rebuses"]:
                if rebus["id"] == rebus_id:
                    rebus["images"].extend(filenames)
                    save_data(data)
                    return jsonify(data)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>/reorder-images", methods=["PUT"])
def reorder_images(level_id, rebus_id):
    data = load_data()
    body = request.get_json()
    order = body.get("order", [])
    for level in data["levels"]:
        if level["id"] == level_id:
            for rebus in level["rebuses"]:
                if rebus["id"] == rebus_id:
                    existing = set(rebus["images"])
                    rebus["images"] = [img for img in order if img in existing]
                    save_data(data)
                    return jsonify(data)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>/upload-url", methods=["POST"])
def upload_image_url(level_id, rebus_id):
    data = load_data()
    body = request.get_json()
    url = body.get("url", "")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        filename = process_image(resp.content)
    except Exception as e:
        return jsonify({"error": f"Failed to download image: {e}"}), 400

    for level in data["levels"]:
        if level["id"] == level_id:
            for rebus in level["rebuses"]:
                if rebus["id"] == rebus_id:
                    rebus["images"].append(filename)
                    save_data(data)
                    return jsonify(data)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/levels/<int:level_id>/rebuses/<rebus_id>/images/<image_name>", methods=["DELETE"])
def delete_image(level_id, rebus_id, image_name):
    data = load_data()
    for level in data["levels"]:
        if level["id"] == level_id:
            for rebus in level["rebuses"]:
                if rebus["id"] == rebus_id:
                    if image_name in rebus["images"]:
                        rebus["images"].remove(image_name)
                        path = os.path.join(IMAGES_DIR, image_name)
                        if os.path.exists(path):
                            os.remove(path)
                        save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:level_id>/reorder", methods=["PUT"])
def reorder_rebuses(level_id):
    data = load_data()
    body = request.get_json()
    order = body.get("order", [])
    for level in data["levels"]:
        if level["id"] == level_id:
            id_to_rebus = {r["id"]: r for r in level["rebuses"]}
            level["rebuses"] = []
            for i, rid in enumerate(order):
                if rid in id_to_rebus:
                    r = id_to_rebus[rid]
                    r["order"] = i
                    level["rebuses"].append(r)
            save_data(data)
            return jsonify(data)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/levels/reorder", methods=["PUT"])
def reorder_levels():
    data = load_data()
    body = request.get_json()
    order = body.get("order", [])
    id_to_level = {l["id"]: l for l in data["levels"]}
    data["levels"] = [id_to_level[lid] for lid in order if lid in id_to_level]
    save_data(data)
    return jsonify(data)


@app.route("/api/levels/<int:from_level>/rebuses/<rebus_id>/move/<int:to_level>", methods=["POST"])
def move_rebus(from_level, rebus_id, to_level):
    data = load_data()
    rebus = None
    for level in data["levels"]:
        if level["id"] == from_level:
            rebus = next((r for r in level["rebuses"] if r["id"] == rebus_id), None)
            if rebus:
                level["rebuses"] = [r for r in level["rebuses"] if r["id"] != rebus_id]
            break
    if rebus:
        for level in data["levels"]:
            if level["id"] == to_level:
                rebus["order"] = len(level["rebuses"])
                level["rebuses"].append(rebus)
                break
    save_data(data)
    return jsonify(data)


@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
