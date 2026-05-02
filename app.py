import subprocess
import json
import sys
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")


def extract_stream(url):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to extract stream")
    return json.loads(result.stdout)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        info = extract_stream(url)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500

    stream_url = info.get("url") or (info.get("formats") or [{}])[-1].get("url")
    return jsonify({
        "title": info.get("title", "Stream"),
        "url": stream_url,
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "ext": info.get("ext", "mp4"),
    })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
