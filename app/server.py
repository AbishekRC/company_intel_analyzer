from flask import Flask, render_template, request, redirect, send_file, jsonify, flash, url_for
import os
import threading
import json
from company_intel_analyzer import run_company_intel, PROGRESS_FILE, MASTER_OUTPUT_FILE

app = Flask(__name__)
app.secret_key = "your_unique_secret_key_here"

# Absolute path for data folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_FOLDER, exist_ok=True)

# ----------------------
# Home page
# ----------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ----------------------
# File upload
# ----------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        flash("No file part")
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        flash("No selected file")
        return redirect(url_for("index"))

    # Save uploaded file
    filepath = os.path.join(DATA_FOLDER, "companies.xlsx")
    file.save(filepath)
    flash("Company list uploaded successfully!")
    return redirect(url_for("index"))

# ----------------------
# Run analyzer in background
# ----------------------
@app.route("/run", methods=["POST"])
def run():
    def background_job():
        run_company_intel()
    thread = threading.Thread(target=background_job)
    thread.start()
    return jsonify({"status": "started"})

# ----------------------
# Progress API
# ----------------------
@app.route("/progress")
def progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return jsonify({"progress": f.read()})
    return jsonify({"progress": "Not started yet."})


# ----------------------
# Download results
# ----------------------
@app.route("/download")
def download():
    if os.path.exists(MASTER_OUTPUT_FILE):
        return send_file(MASTER_OUTPUT_FILE, as_attachment=True, download_name="company_master.xlsx")
    return "No results available", 404

# ----------------------
# Run Flask app
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
