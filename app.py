from flask import Flask, render_template, abort, g, url_for, request, flash, redirect, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
import firmwares

import os

program_dir = os.path.dirname(os.path.realpath(__file__))

UPLOAD_FOLDER = program_dir + '/tmp/true_d_logo'
FIRMWARE_FOLDER = program_dir + '/tmp/true_d_firmware'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
app.config['FIRMWARE_FOLDER'] = FIRMWARE_FOLDER
app.config['INDEX'] = '/'
app.secret_key = 'Z1Zr/98j3yX_R~XHH!jmN]LXG/,?RA'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/uploads/<filename>', methods=["GET"])
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/firmware/<filename>', methods=["GET"])
def firmware_file(filename):
    return send_from_directory(app.config['FIRMWARE_FOLDER'], filename)


@app.route('/preview_img/<filename>', methods=["GET"])
def preview_img(filename):
    preview_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.isfile(preview_full_path):
        flash('Invalid preview image')
        return redirect(app.config['INDEX'])

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/preview/<filename>', methods=["GET"])
def preview(filename):
    preview_link = '/preview_img/{filename}'.format(filename=filename + ".png")
    firmware_link = '/firmware/{filename}'.format(filename=filename)

    print("Generated Firmware: %s" % filename)
    print("  Preview: %s" % preview_link)
    print("  Firmware: %s" % firmware_link)

    preview_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + ".png")
    if not os.path.isfile(preview_full_path):
        flash('Invalid image')
        return redirect(app.config['INDEX'])

    return render_template("preview.html", firmware_link=firmware_link, preview_img=preview_link)


@app.route('/uploads', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(app.config['INDEX'])

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(app.config['INDEX'])

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(full_path)

        if not validate_image(full_path):
            flash('Invalid image size. It must be 128x64')
            return redirect(app.config['INDEX'])

        firmware_name = generate_firmware_with_logo(filename)
        print("Uploaded Image: %s" % filename)

        return redirect(url_for('preview', filename=firmware_name))


@app.route('/')
def index():
    app.config['INDEX'] = '/'
    return render_template("index.html")


@app.route('/en')
def index_en():
    app.config['INDEX'] = '/en'
    return render_template("index_en.html")


def validate_image(filename):
    im = Image.open(filename)

    if im.size != (128, 64):
        return False

    return True


def image_to_hex(filename):
    im = Image.open(filename)
    converted_image = [0] * (128 * 128)

    for block_row in range(8):
        for col in range(128):
            converted_image[col + block_row * 128] = 0
            for row in range(8):
                y = 7 - row
                rgb = im.getpixel((col, y + block_row * 8))

                if not rgb == (255, 255, 255):
                    converted_image[col + block_row * 128] |= (1 << y)

    return converted_image


def generate_intel_hex(converted_image, start_at):
    intel_hex_format = "%02X%04X00%s"
    results = []

    for hex_idx in range(0, 1024, 16):
        hex_data = "".join([("%02X" % h) for h in converted_image[hex_idx:hex_idx + 16]])
        intel_hex = intel_hex_format % (16, start_at + hex_idx, hex_data)
        crc = "%02X" % crc8(intel_hex)
        results.append(":" + intel_hex + crc)

    return results


def crc8(hex_data):
    total = 0
    for idx in range(0, len(hex_data), 2):
        total += int(hex_data[idx:idx + 2], 16)

    checksum = (~total + 1) & 0x000000FF

    return checksum


def generate_preview(hex_image, preview_path):
    preview_image = Image.new("L", (128, 64))

    for block_row in range(8):
        for col in range(128):
            packed_pixels = hex_image[col + block_row * 128]

            for row in range(8):
                y = 7 - row
                pixel = packed_pixels & (1 << y)

                if pixel != 0:
                    preview_image.putpixel((col, y + block_row * 8), 0)
                else:
                    preview_image.putpixel((col, y + block_row * 8), 255)

    preview_image.save(preview_path)

    return preview_path


def generate_firmware_with_logo(logo_filename):
    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)

    converted = image_to_hex(logo_path)
    generated = generate_intel_hex(converted, 0x7140)

    firmware = firmwares.true_d_rev_2_0_firmware.format(logo="\n".join(generated))
    logo_name, log_ext = os.path.splitext(logo_filename)
    firmware_name = "True_D_V2.0_with_{logo}.ino.hex".format(logo=logo_name)
    firmware_path = os.path.join(app.config['FIRMWARE_FOLDER'], firmware_name)

    preview_name = firmware_name + ".png"
    preview_path = os.path.join(app.config['UPLOAD_FOLDER'], preview_name)
    generate_preview(converted, preview_path)

    fp = open(firmware_path, "w")
    fp.write(firmware)
    fp.close()

    return firmware_name


if __name__ == '__main__':
    app.run()
