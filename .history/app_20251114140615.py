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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2881)
