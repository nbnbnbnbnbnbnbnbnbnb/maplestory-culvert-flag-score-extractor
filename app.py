from flask import Flask, render_template, request, redirect
import os
import cv2
import numpy as np
import PIL
from PIL import Image
from pytesseract import pytesseract
import glob
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from werkzeug.utils import secure_filename

app = Flask(__name__)
upload_folder = "uploads/"
app.config['UPLOAD_FOLDER'] = upload_folder

@app.route("/", methods=['POST'])
def upload_image():
    if request.method == 'POST':
        ign = request.files['ign']
        vid = request.files['vid']
        if ign.filename == '' or vid.filename == '':
            print("No files selected for upload")
            return redirect(request.url)

        ign.filename = 'ign.txt'
        vid.filename = 'vid.mp4'
        ign_filename = secure_filename(ign.filename)
        vid_filename = secure_filename(vid.filename)

        ign.save(os.path.join(app.config['UPLOAD_FOLDER'], ign_filename))
        vid.save(os.path.join(app.config['UPLOAD_FOLDER'], vid_filename))
        print(f"Uploaded files: {ign_filename}, {vid_filename}")

    if not os.path.exists('uploads/images/'):
        os.makedirs('uploads/images/')

    cap = cv2.VideoCapture('uploads/vid.mp4')

    # Check if the video is loaded properly
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return redirect(request.url)

    i = 0
    ret, frame_prev = cap.read()
    if not ret:
        print("Error: Could not read the first frame.")
        cap.release()
        return redirect(request.url)

    # Save the first frame
    cv2.imwrite('uploads/images/ss0.png', frame_prev)
    print("Saved first frame: uploads/images/ss0.png")
    i = 1

    while(cap.isOpened()):
        ret, frame_cur = cap.read()
        if not ret:
            print("Error: Could not read the next frame.")
            break

        # Compare frames and check if there is a significant difference
        diff = cv2.absdiff(frame_prev, frame_cur)
        mean_diff = np.mean(diff)
        print(f"Frame difference: {mean_diff}")  # Debug print
        if mean_diff > 5:  # Adjust threshold
            frame_filename = f'uploads/images/ss{i}.png'
            cv2.imwrite(frame_filename, frame_cur)
            print(f"Saved frame {i}: {frame_filename}")
            frame_prev = frame_cur
        i += 1

    cap.release()
    cv2.destroyAllWindows()

    # Ensure tesseract path is correct
    path_to_tesseract = r"C:\Users\honne\Desktop\Tesseract\tesseract.exe"
    pytesseract.tesseract_cmd = path_to_tesseract

    # Path to IGNs
    path_to_igns = "uploads/ign.txt"
    text = ""
    i = 0

    # Read list of IGNs
    with open(path_to_igns, "r") as igns:
        list_of_igns = igns.read().splitlines()
    print(f"Loaded IGNs from {path_to_igns}: {list_of_igns[:5]}...")  # Print first 5 for debug

    # Process each screenshot
    for x in glob.glob("uploads/images/*.png"):
        img = cv2.imread(x)
        # Resizing the image
        img = cv2.resize(img, None, fx=5, fy=5)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Applying Gaussian blur
        img = cv2.GaussianBlur(img, (3, 3), 0)
        # Otsu thresholding
        retval, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        # Erosion
        kernel = np.ones((3, 3), np.uint8)
        img = cv2.erode(img, kernel, iterations=1)
        cv2.imwrite(f'uploads/extracted/processed{i}.png', img)
        i += 1
        # Extract text
        text += pytesseract.image_to_string(img, config='--psm 6 -l eng+ces+fra+spa') + "\n"

    # Write the raw OCR results to a log file
    with open('log.txt', "w", encoding="utf-8") as f:
        f.write(text)

    # Debug: check the content of extracted text
    print("OCR Text:", text[:500])  # Preview the first 500 characters for debugging

    # Process the extracted text
    array = text.splitlines()
    array = list(filter(None, array))

    seen_igns = []
    res = []
    errors = []
    dupes = []

    # Extract data
    for x in range(len(array)):
        array[x] = array[x].split()
        ign = array[x][0]
        match, percent = process.extractOne(ign, list_of_igns)

        if match not in seen_igns and percent > 70:
            res.append([match, array[x][-2], array[x][-1]])
            seen_igns.append(match)
        elif match in seen_igns:
            dupes.append(array[x])
        else:
            errors.append(array[x])

    # Debug: Check how many results, errors, and dupes we found
    print(f"Found {len(res)} results, {len(errors)} errors, {len(dupes)} duplicates")

    # Write results to CSV files
    def write_to_csv(filename, data):
        with open(filename, "w") as f:
            for row in data:
                f.write(" ".join(row) + "\n")
        print(f"Wrote to {filename} with {len(data)} entries")

    write_to_csv('results.csv', res)
    write_to_csv('errors.csv', errors)
    write_to_csv('dupes.csv', dupes)

    image_folder = 'uploads/images'
    for filename in os.listdir(image_folder):
        file_path = os.path.join(image_folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted {file_path}")
        except Exception as e:
            print(f"Failed to delete {file_path}: {e}")

    return render_template('done.html')


@app.route("/", methods=['GET'])
def land():
    return render_template('main.html')


@app.route("/done", methods=['GET'])
def done():
    return render_template('done.html')


if __name__ == "__main__":
    app.run(port=5000)
