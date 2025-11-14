from flask import Flask, request, jsonify

app = Flask(__name__)

# GET endpoint
@app.get("/")
def hello():
    return jsonify({
        "message": "Hello World!",
        "status": "success"
    })

# POST endpoint
@app.post("/submit")
def submit():
    data = request.json  # menerima JSON body
    return jsonify({
        "received": data,
        "status": "success"
    })

@app.route("/convertStream", methods=["POST"])
def convert_stream():
    data = request.get_json(silent=True) or request.form
    link = data.get("link", "")
    if not link:
        return jsonify({"error": "Parameter 'link' wajib diisi"}), 400

    # Buat ID unik
    stream_id = hashlib.md5(link.encode()).hexdigest()[:10]

    # Jika belum aktif, jalankan FFmpeg
    if stream_id not in active_streams:
        thread = Thread(target=run_ffmpeg_to_hls, args=(link, stream_id), daemon=True)
        thread.start()
        active_streams[stream_id] = {
            "source": link,
            "time": datetime.now(),
            "is_played": False,
            "last_access": datetime.now()
        }

    base_url = request.host_url.rstrip("/")

    return jsonify({
        "id": stream_id,
        "status": "conversion_started",
        "hls_url": f"{base_url}/static/hls/{stream_id}/index.m3u8",
        "player_url": f"{base_url}/play/{stream_id}",
        "start_time": active_streams[stream_id]["time"].strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/streams")
def list_streams():
    """Tampilkan daftar stream aktif"""
    base_url = request.host_url.rstrip("/")
    return jsonify([
        {
            "id": sid,
            "source": data["source"],
            "is_played": data["is_played"],
            "last_access": data["last_access"].strftime("%Y-%m-%d %H:%M:%S"),
            "start_time": data["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "player_url": f"{base_url}/play/{sid}"
        }
        for sid, data in active_streams.items()
    ])


@app.route("/play/<stream_id>")
def play_stream(stream_id):
    """Render halaman player HLS"""
    if stream_id not in active_streams:
        return f"<h2>Stream ID {stream_id} tidak ditemukan.</h2>", 404

    # Tandai sebagai sudah diplay dan update waktu akses terakhir
    active_streams[stream_id]["is_played"] = True
    active_streams[stream_id]["last_access"] = datetime.now()

    hls_path = os.path.join(BASE_HLS_DIR, stream_id, "index.m3u8")

    # tunggu sampai file m3u8 siap
    for _ in range(10):
        if os.path.exists(hls_path):
            break
        time.sleep(1)

    if not os.path.exists(hls_path):
        return f"<h2>Stream {stream_id} belum siap. Coba lagi beberapa detik lagi.</h2>", 503

    hls_url = f"/static/hls/{stream_id}/index.m3u8"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Live Stream {stream_id}</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <style>
            body {{
                background: #000;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            video {{
                width: 80%;
                max-width: 800px;
                border-radius: 12px;
                box-shadow: 0 0 20px rgba(0,0,0,0.5);
            }}
        </style>
    </head>
    <body>
        <video id="video" controls autoplay></video>
        <script>
            const video = document.getElementById('video');
            const src = '{hls_url}';
            function initPlayer() {{
                if (Hls.isSupported()) {{
                    const hls = new Hls();
                    hls.loadSource(src);
                    hls.attachMedia(video);
                    hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
                    hls.on(Hls.Events.ERROR, (e, data) => {{
                        if (data.fatal) {{
                            console.log('Retrying in 3s...');
                            setTimeout(initPlayer, 3000);
                        }}
                    }});
                }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                    video.src = src;
                    video.addEventListener('loadedmetadata', () => video.play());
                }} else {{
                    document.body.innerHTML = '<h2 style="color:white;">Browser tidak mendukung HLS</h2>';
                }}
            }}
            setTimeout(initPlayer, 3000);

            // Kirim ping tiap 30 detik supaya dianggap aktif
            setInterval(() => {{
                fetch('/ping/{stream_id}');
            }}, 30000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/ping/<stream_id>")
def ping_stream(stream_id):
    """Dipanggil otomatis dari player untuk memperbarui last_access"""
    if stream_id in active_streams:
        active_streams[stream_id]["last_access"] = datetime.now()
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2881)
