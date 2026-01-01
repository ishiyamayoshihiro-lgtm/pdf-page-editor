#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF編集Webアプリケーション
(c) 2025 IshiyamaYoshihiro
License: MIT License
"""

import os
from flask import Flask, request, jsonify, render_template, send_from_directory
import fitz  # PyMuPDF
import pypdf
import shutil
import zipfile
import io

app = Flask(__name__)

# --- 設定 ---
UPLOAD_FOLDER = 'uploads'
THUMBNAIL_FOLDER = 'thumbnails'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
# ファイルサイズ制限（50MB）
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# フォルダが存在しない場合は作成
for folder in [UPLOAD_FOLDER, THUMBNAIL_FOLDER, OUTPUT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# 最初にアップロードされたファイル名を記録する変数
original_filename = None

# 履歴管理用フォルダ
HISTORY_FOLDER = 'history'
if not os.path.exists(HISTORY_FOLDER):
    os.makedirs(HISTORY_FOLDER)

# 履歴管理用変数
history_stack = []  # 過去の状態を保存
history_index = -1  # 現在の位置

# --- ヘルパー関数 ---
def _save_history():
    """現在のPDF状態を履歴に保存"""
    global history_stack, history_index

    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return

    # 現在より後の履歴を削除（新しい操作が行われた場合）
    if history_index < len(history_stack) - 1:
        for i in range(history_index + 1, len(history_stack)):
            old_file = os.path.join(HISTORY_FOLDER, f'history_{i}.pdf')
            if os.path.exists(old_file):
                os.remove(old_file)
        history_stack = history_stack[:history_index + 1]

    # 履歴に保存
    history_index += 1
    history_filename = f'history_{history_index}.pdf'
    history_path = os.path.join(HISTORY_FOLDER, history_filename)
    shutil.copy(original_pdf_path, history_path)
    history_stack.append(history_filename)

    # 履歴が多すぎる場合は古いものを削除（最大20個）
    if len(history_stack) > 20:
        old_file = os.path.join(HISTORY_FOLDER, history_stack[0])
        if os.path.exists(old_file):
            os.remove(old_file)
        history_stack.pop(0)
        history_index -= 1

def _regenerate_pdf_and_thumbnails(new_order, message):
    """指定された順序でPDFを再生成し、サムネイルも更新する"""
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    try:
        reader = pypdf.PdfReader(original_pdf_path)
        writer = pypdf.PdfWriter()

        if not new_order and len(reader.pages) > 0:
            new_order = range(len(reader.pages))

        for page_index in new_order:
            if page_index >= len(reader.pages):
                return jsonify({'error': f'無効なページ番号です: {page_index}'}), 400
            writer.add_page(reader.pages[page_index])

        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_temp.pdf')
        with open(temp_filepath, 'wb') as f:
            writer.write(f)

        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        return _generate_thumbnails_and_response(message)

    except Exception as e:
        return jsonify({'error': f'PDFの再生成中にエラーが発生しました: {str(e)}'}), 500

def _generate_thumbnails_and_response(message, download_url=None):
    """現在のuploaded.pdfからサムネイルを生成し、JSONレスポンスを返す"""
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    try:
        shutil.rmtree(app.config['THUMBNAIL_FOLDER'], ignore_errors=True)
        os.makedirs(app.config['THUMBNAIL_FOLDER'])
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        thumbnail_urls = []
        for i in range(page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=72)
            thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], f'page_{i}.png')
            pix.save(thumb_path)
            mtime = os.path.getmtime(thumb_path)
            thumbnail_urls.append(f'/thumbnails/page_{i}.png?t={mtime}')
        doc.close()
        response = {
            'message': message,
            'page_count': page_count,
            'thumbnails': thumbnail_urls
        }
        if download_url:
            response['download_url'] = download_url
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': f'サムネイル生成中にエラーが発生しました: {str(e)}'}), 500

# --- ルート ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/clear_all', methods=['POST'])
def clear_all():
    """アップロードされたPDFとサムネイルをすべて削除する"""
    global original_filename, history_stack, history_index

    original_filename = None
    history_stack = []
    history_index = -1

    for folder in [app.config['UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER'], HISTORY_FOLDER]:
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder)
    return jsonify({'message': 'すべてのページがクリアされました。'})

@app.route('/upload', methods=['POST'])
def upload_file():
    global original_filename

    if 'pdfFile' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    file = request.files['pdfFile']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': '無効なファイル形式です'}), 400

    existing_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_upload.pdf')
    file.save(new_file_path)

    try:
        writer = pypdf.PdfWriter()
        message = ""

        if os.path.exists(existing_pdf_path) and os.path.getsize(existing_pdf_path) > 0:
            reader_existing = pypdf.PdfReader(existing_pdf_path)
            for page in reader_existing.pages:
                writer.add_page(page)
            message = "PDFが追加されました。"
        else:
            # 最初のアップロードの場合、ファイル名を記録
            if original_filename is None:
                # .pdfを除去したベース名を保存
                original_filename = file.filename.rsplit('.pdf', 1)[0] if file.filename.lower().endswith('.pdf') else file.filename
            message = "PDFがアップロードされました。"

        reader_new = pypdf.PdfReader(new_file_path)
        for page in reader_new.pages:
            writer.add_page(page)

        # 一時ファイルに書き出し
        temp_write_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_write.pdf')
        with open(temp_write_path, "wb") as f:
            writer.write(f)

        # アップロードされた一時ファイルを削除
        os.remove(new_file_path)

        # 元のファイルを置き換え
        if os.path.exists(existing_pdf_path):
            os.remove(existing_pdf_path)
        os.rename(temp_write_path, existing_pdf_path)

        # 履歴に保存
        _save_history()

        # サムネイル生成とレスポンス
        return _generate_thumbnails_and_response(message)

    except Exception as e:
        # エラー時は一時ファイルをクリーンアップ
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        return jsonify({'error': f'PDFのアップロード処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/split', methods=['POST'])
def split_pdf():
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    pages_to_split = data.get('pages_to_split')

    try:
        doc = fitz.open(original_pdf_path)
        new_doc = fitz.open()

        if pages_to_split is None:
            target_pages = range(len(doc))
            message = "全ての横長ページを分割しました。"
        elif not pages_to_split:
            return jsonify({'message': '分割するページが選択されていません。'})
        else:
            target_pages = set(pages_to_split)
            message = f'{len(target_pages)}ページを選択して分割処理をしました。'

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            rect = page.rect
            width, height = rect.width, rect.height
            if page_num in target_pages and width > height:
                left_half_rect = fitz.Rect(0, 0, width / 2, height)
                right_half_rect = fitz.Rect(width / 2, 0, width, height)
                new_page_left = new_doc.new_page(width=width / 2, height=height)
                new_page_left.show_pdf_page(new_page_left.rect, doc, page_num, clip=left_half_rect)
                new_page_right = new_doc.new_page(width=width / 2, height=height)
                new_page_right.show_pdf_page(new_page_right.rect, doc, page_num, clip=right_half_rect)
            else:
                new_page = new_doc.new_page(width=width, height=height)
                new_page.show_pdf_page(new_page.rect, doc, page_num)

        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_temp.pdf')
        new_doc.save(temp_filepath, garbage=4, deflate=True, clean=True)
        doc.close()
        new_doc.close()
        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        output_filename = 'split.pdf'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        shutil.copy(original_pdf_path, output_path)

        return _generate_thumbnails_and_response(message, f'/download/{output_filename}')

    except Exception as e:
        return jsonify({'error': f'PDFの分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/delete', methods=['POST'])
def delete_pages():
    data = request.get_json()
    if not data or 'pages_to_delete' not in data:
        return jsonify({'error': '削除するページが指定されていません'}), 400
    pages_to_delete = set([int(i) for i in data['pages_to_delete']])
    reader = pypdf.PdfReader(os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf'))
    new_order = [i for i in range(len(reader.pages)) if i not in pages_to_delete]
    return _regenerate_pdf_and_thumbnails(new_order, f'{len(pages_to_delete)}ページを削除しました')

@app.route('/rotate', methods=['POST'])
def rotate_pages():
    data = request.get_json()
    if not data or 'pages' not in data or 'rotation' not in data:
        return jsonify({'error': '回転するページと角度が指定されていません'}), 400

    pages_to_rotate = [int(i) for i in data['pages']]
    rotation = int(data['rotation'])
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    try:
        reader = pypdf.PdfReader(original_pdf_path)
        writer = pypdf.PdfWriter()
        for page_index in range(len(reader.pages)):
            page = reader.pages[page_index]
            if page_index in pages_to_rotate:
                page.rotate(rotation)
            writer.add_page(page)

        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_temp.pdf')
        with open(temp_filepath, 'wb') as f:
            writer.write(f)

        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        return _generate_thumbnails_and_response(f'{len(pages_to_rotate)}ページを回転しました')

    except Exception as e:
        return jsonify({'error': f'ページの回転中にエラーが発生しました: {str(e)}'}), 500

@app.route('/reorder', methods=['POST'])
def reorder_pdf():
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': '順序データがありません'}), 400
    new_order = [int(i) for i in data['order']]
    custom_filename = data.get('filename', 'reordered')  # カスタムファイル名を取得（デフォルトは'reordered'）
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    try:
        reader = pypdf.PdfReader(original_pdf_path)
        writer = pypdf.PdfWriter()
        if len(new_order) != len(reader.pages):
            return jsonify({'error': 'ページ数が一致しません'}), 400
        for page_index in new_order:
            writer.add_page(reader.pages[page_index])
        # .pdfがすでに含まれている場合は除去してから追加
        if custom_filename.lower().endswith('.pdf'):
            custom_filename = custom_filename[:-4]
        output_filename = f'{custom_filename}.pdf'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'wb') as f:
            writer.write(f)
        return jsonify({'download_url': f'/download/{output_filename}', 'filename': output_filename})
    except Exception as e:
        return jsonify({'error': f'PDFの並べ替え中にエラーが発生しました: {str(e)}'}), 500

@app.route('/swap_odd_even', methods=['POST'])
def swap_odd_even():
    reader = pypdf.PdfReader(os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf'))
    page_count = len(reader.pages)
    new_order = []
    for i in range(0, page_count - 1, 2):
        new_order.extend([i + 1, i])
    if page_count % 2 != 0:
        new_order.append(page_count - 1)
    return _regenerate_pdf_and_thumbnails(new_order, "偶数・奇数ページを入れ替えました。")

@app.route('/reverse_all', methods=['POST'])
def reverse_all():
    reader = pypdf.PdfReader(os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf'))
    page_count = len(reader.pages)
    new_order = list(range(page_count - 1, -1, -1))
    return _regenerate_pdf_and_thumbnails(new_order, "全ページを逆順にしました。")

@app.route('/apply_mask', methods=['POST'])
def apply_mask():
    """指定された領域を指定されたページ間隔とオフセットで黒塗りする"""
    data = request.get_json()
    if not data or 'mask' not in data:
        return jsonify({'error': 'マスク領域が指定されていません'}), 400

    mask = data['mask']  # {x, y, width, height} - 正規化された座標 (0-1)
    interval = data.get('interval', 1)  # ページ間隔（デフォルト: 1）
    offset = data.get('offset', 1)  # オフセット（デフォルト: 1 = 1ページ目）
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    try:
        doc = fitz.open(original_pdf_path)
        new_doc = fitz.open()

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            rect = page.rect

            # 新しいドキュメントにページをコピー
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num)

            # ページ間隔とオフセットに基づいてマスキングを適用するかチェック
            # offset=1, interval=2: 1ページ目から2ページおき (0,2,4,6,...) → page_num % interval == 0
            # offset=2, interval=2: 2ページ目から2ページおき (1,3,5,7,...) → page_num % interval == 1
            # offset=3, interval=3: 3ページ目から3ページおき (2,5,8,11,...) → page_num % interval == 2
            # つまり: (page_num + 1) が offset と同じ余りを interval で割ったとき一致
            if (page_num + 1 - offset) % interval == 0 and page_num >= offset - 1:
                # 正規化された座標を実際のページ座標に変換
                mask_rect = fitz.Rect(
                    rect.width * mask['x'],
                    rect.height * mask['y'],
                    rect.width * (mask['x'] + mask['width']),
                    rect.height * (mask['y'] + mask['height'])
                )

                # 新しいページに黒い矩形を描画
                shape = new_page.new_shape()
                shape.draw_rect(mask_rect)
                shape.finish(color=(0, 0, 0), fill=(0, 0, 0))  # 黒塗り
                shape.commit()

        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_temp.pdf')
        new_doc.save(temp_filepath, garbage=4, deflate=True, clean=True)
        doc.close()
        new_doc.close()

        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        # メッセージを生成
        if interval == 1 and offset == 1:
            message = '全ページにマスキングを適用しました。'
        else:
            message = f'{interval}ページ毎に{offset}ページ目にマスキングを適用しました。'

        return _generate_thumbnails_and_response(message)

    except Exception as e:
        return jsonify({'error': f'マスキング処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/undo', methods=['POST'])
def undo():
    """一つ前の状態に戻す"""
    global history_index

    # history_index は現在の状態を指している
    # 一つ前に戻すには history_index - 1 の状態を復元する
    if history_index < 1:
        return jsonify({'error': 'これ以上戻せません'}), 400

    try:
        # 一つ前の履歴を取得
        history_index -= 1
        history_filename = history_stack[history_index]
        history_path = os.path.join(HISTORY_FOLDER, history_filename)


        if not os.path.exists(history_path):
            return jsonify({'error': '履歴ファイルが見つかりません'}), 400

        # PDFを復元
        original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
        shutil.copy(history_path, original_pdf_path)

        return _generate_thumbnails_and_response('1つ前の状態に戻しました')

    except Exception as e:
        return jsonify({'error': f'元に戻す処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/redo', methods=['POST'])
def redo():
    """一つ先の状態に進む"""
    global history_index

    if history_index >= len(history_stack) - 1:
        return jsonify({'error': 'これ以上進めません'}), 400

    try:
        # 一つ先の履歴を取得
        history_index += 1
        history_filename = history_stack[history_index]
        history_path = os.path.join(HISTORY_FOLDER, history_filename)

        if not os.path.exists(history_path):
            return jsonify({'error': '履歴ファイルが見つかりません'}), 400

        # PDFを復元
        original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
        shutil.copy(history_path, original_pdf_path)

        return _generate_thumbnails_and_response('1つ先の状態に進みました')

    except Exception as e:
        return jsonify({'error': f'やり直す処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/history_status', methods=['GET'])
def history_status():
    """Undo/Redoが可能かどうかを返す"""
    can_undo = history_index >= 1
    can_redo = history_index < len(history_stack) - 1
    return jsonify({'can_undo': can_undo, 'can_redo': can_redo})

@app.route('/get_original_filename', methods=['GET'])
def get_original_filename():
    """最初にアップロードされたファイル名を返す"""
    return jsonify({'filename': original_filename or 'edited'})

@app.route('/split_to_files', methods=['POST'])
def split_to_files():
    """各ページを個別のPDFファイルとして保存し、ZIPでダウンロード"""
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    convert_to_image = data.get('convert_to_image', False)
    dpi = data.get('dpi', 150)

    try:
        # ベースファイル名を取得
        base_filename = original_filename or 'page'

        # ZIPファイルをメモリ上に作成
        zip_buffer = io.BytesIO()

        if convert_to_image:
            # 画像PDFとして保存
            doc = fitz.open(original_pdf_path)
            page_count = len(doc)

            if page_count == 0:
                return jsonify({'error': 'PDFにページがありません'}), 400

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for page_index in range(page_count):
                    page = doc.load_page(page_index)

                    # ページを画像としてレンダリング
                    pix = page.get_pixmap(dpi=dpi)
                    img_bytes = pix.tobytes("png")

                    # 新しいPDFドキュメントを作成
                    new_doc = fitz.open()
                    rect = page.rect
                    new_page = new_doc.new_page(width=rect.width, height=rect.height)
                    img_rect = fitz.Rect(0, 0, rect.width, rect.height)
                    new_page.insert_image(img_rect, stream=img_bytes)

                    # PDFをメモリに書き込み
                    pdf_buffer = io.BytesIO()
                    new_doc.save(pdf_buffer, garbage=4, deflate=True, clean=True)
                    pdf_buffer.seek(0)

                    # ZIPファイルに追加
                    page_filename = f'{base_filename}_{page_index + 1}.pdf'
                    zip_file.writestr(page_filename, pdf_buffer.read())

                    new_doc.close()

            doc.close()
            message = f'{page_count}ページを画像PDFとして個別ファイルに分割しました（{dpi} DPI）'

        else:
            # 通常のPDFとして保存
            reader = pypdf.PdfReader(original_pdf_path)
            page_count = len(reader.pages)

            if page_count == 0:
                return jsonify({'error': 'PDFにページがありません'}), 400

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for page_index in range(page_count):
                    # 各ページ用の新しいPDFを作成
                    writer = pypdf.PdfWriter()
                    writer.add_page(reader.pages[page_index])

                    # PDFをメモリ上に書き込み
                    pdf_buffer = io.BytesIO()
                    writer.write(pdf_buffer)
                    pdf_buffer.seek(0)

                    # ZIPファイルに追加
                    page_filename = f'{base_filename}_{page_index + 1}.pdf'
                    zip_file.writestr(page_filename, pdf_buffer.read())

            message = f'{page_count}ページを個別のPDFファイルに分割しました'

        # ZIPファイルを保存
        zip_filename = f'{base_filename}_pages.zip'
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)

        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.getvalue())

        return jsonify({
            'message': message,
            'download_url': f'/download/{zip_filename}',
            'filename': zip_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'ページ分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/convert_to_image_pdf', methods=['POST'])
def convert_to_image_pdf():
    """PDFを画像ベースのPDFに変換（フォント問題を回避）"""
    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    dpi = data.get('dpi', 150)  # デフォルトは150 DPI
    custom_filename = data.get('filename', original_filename or 'image_pdf')

    try:
        # 元のPDFを開く
        doc = fitz.open(original_pdf_path)
        page_count = len(doc)

        if page_count == 0:
            return jsonify({'error': 'PDFにページがありません'}), 400

        # 新しいPDFドキュメントを作成
        new_doc = fitz.open()

        for page_num in range(page_count):
            page = doc.load_page(page_num)

            # ページを指定されたDPIで画像としてレンダリング
            pix = page.get_pixmap(dpi=dpi)

            # 画像をPNGバイトとして取得
            img_bytes = pix.tobytes("png")

            # 新しいPDFページを作成（元のページサイズと同じ）
            rect = page.rect
            new_page = new_doc.new_page(width=rect.width, height=rect.height)

            # 画像を新しいページに挿入
            img_rect = fitz.Rect(0, 0, rect.width, rect.height)
            new_page.insert_image(img_rect, stream=img_bytes)

        # 出力ファイル名を準備
        if custom_filename.lower().endswith('.pdf'):
            custom_filename = custom_filename[:-4]
        output_filename = f'{custom_filename}_image.pdf'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        # 新しいPDFを保存
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)

        doc.close()
        new_doc.close()

        return jsonify({
            'message': f'{page_count}ページを画像PDFに変換しました（{dpi} DPI）',
            'download_url': f'/download/{output_filename}',
            'filename': output_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'画像PDF変換中にエラーが発生しました: {str(e)}'}), 500

@app.route('/split_and_save', methods=['POST'])
def split_and_save():
    """分割線で区切られた各パートに名前を付けて保存"""
    global original_filename

    original_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.pdf')
    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json()
    if not data or 'parts' not in data:
        return jsonify({'error': 'パート情報が指定されていません'}), 400

    parts = data['parts']  # [{'filename': 'xxx', 'save': True, 'start': 0, 'end': 3}, ...]

    try:
        reader = pypdf.PdfReader(original_pdf_path)

        # 保存するパートをフィルタリング
        parts_to_save = [p for p in parts if p.get('save', True)]

        if not parts_to_save:
            return jsonify({'error': '保存するパートが選択されていません'}), 400

        # 各パートのPDFファイルを個別に保存
        download_urls = []

        for part in parts_to_save:
            filename = part.get('filename', '').strip()
            if not filename:
                continue

            start_page = int(part['start'])
            end_page = int(part['end'])

            # パートのPDFを作成
            writer = pypdf.PdfWriter()
            for page_index in range(start_page, end_page):
                if page_index < len(reader.pages):
                    writer.add_page(reader.pages[page_index])

            # .pdfがない場合は追加
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'

            # PDFファイルを保存
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            with open(output_path, 'wb') as f:
                writer.write(f)

            download_urls.append({
                'url': f'/download/{filename}',
                'filename': filename
            })

        return jsonify({
            'message': f'{len(parts_to_save)}個のファイルに分割しました',
            'files': download_urls
        })

    except Exception as e:
        return jsonify({'error': f'ファイル分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)

@app.route('/download/<path:filename>')
def serve_output(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    import os
    # 環境変数で本番環境かどうかを判定（PythonAnywhereではFLASK_ENV=productionを設定）
    is_production = os.environ.get('FLASK_ENV') == 'production'

    if not is_production:
        print("=" * 60)
        print("アプリケーションを起動しています...")
        print("Webブラウザで http://127.0.0.1:5000 を開いてください")
        print("=" * 60)

    app.run(host='127.0.0.1', port=5000, debug=not is_production)
