import subprocess
import json
import sys
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

app = Flask(__name__, static_folder="static")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def extract_stream(url):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-playlist",
        "--no-check-certificates",
        "--user-agent", UA,
        "--referer", url,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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

    formats = info.get("formats") or []
    stream_url = info.get("url") or (formats[-1].get("url") if formats else None)
    ext = info.get("ext", "")

    # Detect HLS
    is_hls = ext == "m3u8" or (stream_url and ".m3u8" in stream_url)

    return jsonify({
        "title": info.get("title", "Stream"),
        "url": stream_url,
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "ext": ext,
        "is_hls": is_hls,
        "referer": url,
    })


@app.route("/proxy")
def proxy():
    stream_url = request.args.get("url", "").strip()
    referer = request.args.get("referer", "").strip()
    if not stream_url:
        return "Missing url", 400

    req = urllib.request.Request(stream_url)
    req.add_header("User-Agent", UA)
    if referer:
        req.add_header("Referer", referer)
        req.add_header("Origin", referer.rsplit("/", 1)[0])

    try:
        remote = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        return f"Upstream error: {e.code}", 502
    except Exception as e:
        return f"Proxy error: {e}", 502

    content_type = remote.headers.get("Content-Type", "application/octet-stream")

    def generate():
        while True:
            chunk = remote.read(65536)
            if not chunk:
                break
            yield chunk

    return Response(stream_with_context(generate()), content_type=content_type)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=False)
