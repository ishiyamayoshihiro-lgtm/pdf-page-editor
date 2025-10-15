
import os
from flask import Flask, request, jsonify, render_template, send_from_directory
import fitz  # PyMuPDF
import pypdf
import shutil

app = Flask(__name__)

# --- 設定 ---
UPLOAD_FOLDER = 'uploads'
THUMBNAIL_FOLDER = 'thumbnails'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# フォルダが存在しない場合は作成
for folder in [UPLOAD_FOLDER, THUMBNAIL_FOLDER, OUTPUT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

@app.route('/')
def index():
    """メインページを表示"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """PDFをアップロードし、サムネイルを生成する"""
    if 'pdfFile' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    
    file = request.files['pdfFile']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    if file and file.filename.lower().endswith('.pdf'):
        # 既存のファイルをクリーンアップ
        shutil.rmtree(app.config['THUMBNAIL_FOLDER'], ignore_errors=True)
        os.makedirs(app.config['THUMBNAIL_FOLDER'])

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
        file.save(filepath)

        try:
            doc = fitz.open(filepath)
            page_count = len(doc)
            thumbnail_urls = []

            for i in range(page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=72)
                thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], f'page_{i}.png')
                pix.save(thumb_path)
                thumbnail_urls.append(f'/thumbnails/page_{i}.png')
            
            doc.close()
            return jsonify({'page_count': page_count, 'thumbnails': thumbnail_urls})
        except Exception as e:
            return jsonify({'error': f'PDFの処理中にエラーが発生しました: {str(e)}'}), 500
    
    return jsonify({'error': '無効なファイル形式です'}), 400

@app.route('/reorder', methods=['POST'])
def reorder_pdf():
    """指定された順序でPDFを並べ替えて保存する"""
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': '順序データがありません'}), 400

    new_order = [int(i) for i in data['order']]
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')

    try:
        reader = pypdf.PdfReader(original_pdf_path)
        writer = pypdf.PdfWriter()

        if len(new_order) != len(reader.pages):
            return jsonify({'error': 'ページ数が一致しません'}), 400

        for page_index in new_order:
            writer.add_page(reader.pages[page_index])
        
        output_filename = 'reordered.pdf'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return jsonify({'download_url': f'/download/{output_filename}'})
    except Exception as e:
        return jsonify({'error': f'PDFの並べ替え中にエラーが発生しました: {str(e)}'}), 500

@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """サムネイル画像を提供する"""
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)

@app.route('/download/<path:filename>')
def serve_output(filename):
    """完成したPDFを提供する"""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    print(" * アプリケーションを起動しています...")
    print(" * Webブラウザで http://127.0.0.1:5000 を開いてください")
    app.run(host='127.0.0.1', port=5000, debug=False)
