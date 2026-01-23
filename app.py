#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF編集Webアプリケーション
(c) 2025 IshiyamaYoshihiro
License: MIT License
"""

import os
import uuid
import time
import threading
from flask import Flask, request, jsonify, render_template, send_from_directory, session
import fitz  # PyMuPDF
import pypdf
import shutil
import zipfile
import io

app = Flask(__name__)

# --- 設定 ---
# セッション用のシークレットキー（本番環境では環境変数から取得すること）
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ベースフォルダ（セッションごとのサブフォルダがこの下に作成される）
BASE_UPLOAD_FOLDER = 'uploads'
BASE_THUMBNAIL_FOLDER = 'thumbnails'
BASE_OUTPUT_FOLDER = 'output'
BASE_HISTORY_FOLDER = 'history'

# ファイルサイズ制限（500MB）
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# セッションの有効期限（秒）- 2時間
SESSION_LIFETIME = 2 * 60 * 60

# ベースフォルダが存在しない場合は作成
for folder in [BASE_UPLOAD_FOLDER, BASE_THUMBNAIL_FOLDER, BASE_OUTPUT_FOLDER, BASE_HISTORY_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# セッションごとの状態を管理する辞書
session_data = {}
session_data_lock = threading.Lock()


def get_session_id():
    """現在のセッションIDを取得（なければ新規作成）"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        # 新しいセッション用のフォルダを作成
        _ensure_session_folders(session['session_id'])
        # セッションデータを初期化
        with session_data_lock:
            session_data[session['session_id']] = {
                'original_filename': None,
                'history_stack': [],
                'history_index': -1,
                'last_access': time.time()
            }
    else:
        # アクセス時間を更新
        with session_data_lock:
            if session['session_id'] in session_data:
                session_data[session['session_id']]['last_access'] = time.time()
    return session['session_id']


def _ensure_session_folders(session_id):
    """セッション用のフォルダを作成"""
    folders = [
        os.path.join(BASE_UPLOAD_FOLDER, session_id),
        os.path.join(BASE_THUMBNAIL_FOLDER, session_id),
        os.path.join(BASE_OUTPUT_FOLDER, session_id),
        os.path.join(BASE_HISTORY_FOLDER, session_id)
    ]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)


def get_session_paths():
    """現在のセッション用のパスを取得"""
    session_id = get_session_id()
    return {
        'upload': os.path.join(BASE_UPLOAD_FOLDER, session_id),
        'thumbnail': os.path.join(BASE_THUMBNAIL_FOLDER, session_id),
        'output': os.path.join(BASE_OUTPUT_FOLDER, session_id),
        'history': os.path.join(BASE_HISTORY_FOLDER, session_id)
    }


def get_session_data():
    """現在のセッションのデータを取得"""
    session_id = get_session_id()
    with session_data_lock:
        if session_id not in session_data:
            session_data[session_id] = {
                'original_filename': None,
                'history_stack': [],
                'history_index': -1,
                'last_access': time.time()
            }
        return session_data[session_id]


def cleanup_old_sessions():
    """古いセッションのファイルをクリーンアップ"""
    current_time = time.time()
    sessions_to_remove = []

    with session_data_lock:
        for sid, data in session_data.items():
            if current_time - data['last_access'] > SESSION_LIFETIME:
                sessions_to_remove.append(sid)

    for sid in sessions_to_remove:
        # セッションのフォルダを削除
        for base_folder in [BASE_UPLOAD_FOLDER, BASE_THUMBNAIL_FOLDER, BASE_OUTPUT_FOLDER, BASE_HISTORY_FOLDER]:
            folder_path = os.path.join(base_folder, sid)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)

        # セッションデータを削除
        with session_data_lock:
            if sid in session_data:
                del session_data[sid]


# 定期的にクリーンアップを実行するバックグラウンドスレッド
def cleanup_thread():
    while True:
        time.sleep(30 * 60)  # 30分ごとにチェック
        cleanup_old_sessions()

# バックグラウンドでクリーンアップスレッドを開始
cleanup_worker = threading.Thread(target=cleanup_thread, daemon=True)
cleanup_worker.start()

# --- ヘルパー関数 ---
def _save_history():
    """現在のPDF状態を履歴に保存"""
    paths = get_session_paths()
    data = get_session_data()

    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return

    # 現在より後の履歴を削除（新しい操作が行われた場合）
    if data['history_index'] < len(data['history_stack']) - 1:
        for i in range(data['history_index'] + 1, len(data['history_stack'])):
            old_file = os.path.join(paths['history'], f'history_{i}.pdf')
            if os.path.exists(old_file):
                os.remove(old_file)
        data['history_stack'] = data['history_stack'][:data['history_index'] + 1]

    # 履歴に保存
    data['history_index'] += 1
    history_filename = f'history_{data["history_index"]}.pdf'
    history_path = os.path.join(paths['history'], history_filename)
    shutil.copy(original_pdf_path, history_path)
    data['history_stack'].append(history_filename)

    # 履歴が多すぎる場合は古いものを削除（最大20個）
    if len(data['history_stack']) > 20:
        old_file = os.path.join(paths['history'], data['history_stack'][0])
        if os.path.exists(old_file):
            os.remove(old_file)
        data['history_stack'].pop(0)
        data['history_index'] -= 1

def _regenerate_pdf_and_thumbnails(new_order, message):
    """指定された順序でPDFを再生成し、サムネイルも更新する"""
    paths = get_session_paths()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
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

        temp_filepath = os.path.join(paths['upload'], 'uploaded_temp.pdf')
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
    paths = get_session_paths()
    session_id = get_session_id()
    pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
    try:
        shutil.rmtree(paths['thumbnail'], ignore_errors=True)
        os.makedirs(paths['thumbnail'])
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        thumbnail_urls = []
        for i in range(page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=72)
            thumb_path = os.path.join(paths['thumbnail'], f'page_{i}.png')
            pix.save(thumb_path)
            mtime = os.path.getmtime(thumb_path)
            thumbnail_urls.append(f'/thumbnails/{session_id}/page_{i}.png?t={mtime}')
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
    paths = get_session_paths()
    data = get_session_data()

    data['original_filename'] = None
    data['history_stack'] = []
    data['history_index'] = -1

    for folder in [paths['upload'], paths['thumbnail'], paths['history']]:
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder)
    return jsonify({'message': 'すべてのページがクリアされました。'})

@app.route('/upload', methods=['POST'])
def upload_file():
    paths = get_session_paths()
    data = get_session_data()

    if 'pdfFile' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    file = request.files['pdfFile']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': '無効なファイル形式です'}), 400

    existing_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
    new_file_path = os.path.join(paths['upload'], 'temp_upload.pdf')
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
            if data['original_filename'] is None:
                # .pdfを除去したベース名を保存
                data['original_filename'] = file.filename.rsplit('.pdf', 1)[0] if file.filename.lower().endswith('.pdf') else file.filename
            message = "PDFがアップロードされました。"

        reader_new = pypdf.PdfReader(new_file_path)
        for page in reader_new.pages:
            writer.add_page(page)

        # 一時ファイルに書き出し
        temp_write_path = os.path.join(paths['upload'], 'temp_write.pdf')
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
    paths = get_session_paths()
    session_id = get_session_id()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
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

        temp_filepath = os.path.join(paths['upload'], 'uploaded_temp.pdf')
        new_doc.save(temp_filepath, garbage=4, deflate=True, clean=True)
        doc.close()
        new_doc.close()
        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        output_filename = 'split.pdf'
        output_path = os.path.join(paths['output'], output_filename)
        shutil.copy(original_pdf_path, output_path)

        return _generate_thumbnails_and_response(message, f'/download/{session_id}/{output_filename}')

    except Exception as e:
        return jsonify({'error': f'PDFの分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/delete', methods=['POST'])
def delete_pages():
    paths = get_session_paths()
    data = request.get_json()
    if not data or 'pages_to_delete' not in data:
        return jsonify({'error': '削除するページが指定されていません'}), 400
    pages_to_delete = set([int(i) for i in data['pages_to_delete']])
    reader = pypdf.PdfReader(os.path.join(paths['upload'], 'uploaded.pdf'))
    new_order = [i for i in range(len(reader.pages)) if i not in pages_to_delete]
    return _regenerate_pdf_and_thumbnails(new_order, f'{len(pages_to_delete)}ページを削除しました')

@app.route('/rotate', methods=['POST'])
def rotate_pages():
    paths = get_session_paths()
    data = request.get_json()
    if not data or 'pages' not in data or 'rotation' not in data:
        return jsonify({'error': '回転するページと角度が指定されていません'}), 400

    pages_to_rotate = [int(i) for i in data['pages']]
    rotation = int(data['rotation'])
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
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

        temp_filepath = os.path.join(paths['upload'], 'uploaded_temp.pdf')
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
    paths = get_session_paths()
    session_id = get_session_id()
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': '順序データがありません'}), 400
    new_order = [int(i) for i in data['order']]
    custom_filename = data.get('filename', 'reordered')  # カスタムファイル名を取得（デフォルトは'reordered'）
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
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
        output_path = os.path.join(paths['output'], output_filename)
        with open(output_path, 'wb') as f:
            writer.write(f)
        return jsonify({'download_url': f'/download/{session_id}/{output_filename}', 'filename': output_filename})
    except Exception as e:
        return jsonify({'error': f'PDFの並べ替え中にエラーが発生しました: {str(e)}'}), 500

@app.route('/apply_reorder', methods=['POST'])
def apply_reorder():
    """ページの並べ替えを適用してPDFを更新する"""
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': '順序データがありません'}), 400
    new_order = [int(i) for i in data['order']]
    return _regenerate_pdf_and_thumbnails(new_order, 'ページの並べ替えを適用しました')

@app.route('/swap_odd_even', methods=['POST'])
def swap_odd_even():
    paths = get_session_paths()
    reader = pypdf.PdfReader(os.path.join(paths['upload'], 'uploaded.pdf'))
    page_count = len(reader.pages)
    new_order = []
    for i in range(0, page_count - 1, 2):
        new_order.extend([i + 1, i])
    if page_count % 2 != 0:
        new_order.append(page_count - 1)
    return _regenerate_pdf_and_thumbnails(new_order, "偶数・奇数ページを入れ替えました。")

@app.route('/reverse_all', methods=['POST'])
def reverse_all():
    paths = get_session_paths()
    reader = pypdf.PdfReader(os.path.join(paths['upload'], 'uploaded.pdf'))
    page_count = len(reader.pages)
    new_order = list(range(page_count - 1, -1, -1))
    return _regenerate_pdf_and_thumbnails(new_order, "全ページを逆順にしました。")

@app.route('/apply_mask', methods=['POST'])
def apply_mask():
    """指定された領域を指定されたページ間隔とオフセットで黒塗りする"""
    paths = get_session_paths()
    data = request.get_json()
    if not data or 'mask' not in data:
        return jsonify({'error': 'マスク領域が指定されていません'}), 400

    mask = data['mask']  # {x, y, width, height} - 正規化された座標 (0-1)
    interval = data.get('interval', 1)  # ページ間隔（デフォルト: 1）
    offset = data.get('offset', 1)  # オフセット（デフォルト: 1 = 1ページ目）
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

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

        temp_filepath = os.path.join(paths['upload'], 'uploaded_temp.pdf')
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

def _draw_symbol(page, symbol, center_x, center_y, size):
    """シンボルを図形として描画する"""
    shape = page.new_shape()
    half_size = size / 2

    if symbol == '■':  # 黒四角
        rect = fitz.Rect(center_x - half_size, center_y - half_size,
                         center_x + half_size, center_y + half_size)
        shape.draw_rect(rect)
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
    elif symbol == '□':  # 白四角
        rect = fitz.Rect(center_x - half_size, center_y - half_size,
                         center_x + half_size, center_y + half_size)
        shape.draw_rect(rect)
        shape.finish(color=(0, 0, 0), fill=None, width=1)
    elif symbol == '◆':  # 黒ダイヤ
        points = [
            fitz.Point(center_x, center_y - half_size),
            fitz.Point(center_x + half_size, center_y),
            fitz.Point(center_x, center_y + half_size),
            fitz.Point(center_x - half_size, center_y),
        ]
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
    elif symbol == '◇':  # 白ダイヤ
        points = [
            fitz.Point(center_x, center_y - half_size),
            fitz.Point(center_x + half_size, center_y),
            fitz.Point(center_x, center_y + half_size),
            fitz.Point(center_x - half_size, center_y),
        ]
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=None, width=1)
    elif symbol == '●':  # 黒丸
        shape.draw_circle(fitz.Point(center_x, center_y), half_size)
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
    elif symbol == '○':  # 白丸
        shape.draw_circle(fitz.Point(center_x, center_y), half_size)
        shape.finish(color=(0, 0, 0), fill=None, width=1)
    elif symbol == '★':  # 黒星（5角星）
        import math
        points = []
        for i in range(5):
            # 外側の点
            angle = math.radians(-90 + i * 72)
            points.append(fitz.Point(center_x + half_size * math.cos(angle),
                                     center_y + half_size * math.sin(angle)))
            # 内側の点
            angle = math.radians(-90 + i * 72 + 36)
            points.append(fitz.Point(center_x + half_size * 0.4 * math.cos(angle),
                                     center_y + half_size * 0.4 * math.sin(angle)))
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
    elif symbol == '☆':  # 白星（5角星）
        import math
        points = []
        for i in range(5):
            angle = math.radians(-90 + i * 72)
            points.append(fitz.Point(center_x + half_size * math.cos(angle),
                                     center_y + half_size * math.sin(angle)))
            angle = math.radians(-90 + i * 72 + 36)
            points.append(fitz.Point(center_x + half_size * 0.4 * math.cos(angle),
                                     center_y + half_size * 0.4 * math.sin(angle)))
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=None, width=1)
    elif symbol == '▲':  # 黒三角
        points = [
            fitz.Point(center_x, center_y - half_size),
            fitz.Point(center_x + half_size, center_y + half_size),
            fitz.Point(center_x - half_size, center_y + half_size),
        ]
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
    elif symbol == '△':  # 白三角
        points = [
            fitz.Point(center_x, center_y - half_size),
            fitz.Point(center_x + half_size, center_y + half_size),
            fitz.Point(center_x - half_size, center_y + half_size),
        ]
        shape.draw_polyline(points + [points[0]])
        shape.finish(color=(0, 0, 0), fill=None, width=1)

    shape.commit()


@app.route('/apply_symbols', methods=['POST'])
def apply_symbols():
    """シンボルマークを全ページの四隅に追加する"""
    paths = get_session_paths()
    data = request.get_json()
    if not data or 'symbols' not in data:
        return jsonify({'error': 'シンボル設定が指定されていません'}), 400

    symbols = data['symbols']  # {'topleft': {'symbol': '■', 'x': 20, 'y': 20}, ...}
    symbol_size = data.get('size', 14)  # シンボルサイズ（デフォルト: 14pt）
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    if not symbols:
        return jsonify({'error': '少なくとも1つのシンボルを選択してください'}), 400

    try:
        doc = fitz.open(original_pdf_path)
        new_doc = fitz.open()

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            rect = page.rect

            # 新しいドキュメントにページをコピー
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num)

            # 各コーナーにシンボルを追加
            for corner, settings in symbols.items():
                symbol = settings['symbol']
                x_offset = settings['x']  # ポイント
                y_offset = settings['y']  # ポイント

                # コーナーに応じて中心位置を計算
                if corner == 'topleft':
                    center_x = x_offset
                    center_y = y_offset
                elif corner == 'topright':
                    center_x = rect.width - x_offset
                    center_y = y_offset
                elif corner == 'bottomleft':
                    center_x = x_offset
                    center_y = rect.height - y_offset
                elif corner == 'bottomright':
                    center_x = rect.width - x_offset
                    center_y = rect.height - y_offset
                else:
                    continue

                # シンボルを図形として描画
                _draw_symbol(new_page, symbol, center_x, center_y, symbol_size)

        temp_filepath = os.path.join(paths['upload'], 'uploaded_temp.pdf')
        new_doc.save(temp_filepath, garbage=4, deflate=True, clean=True)
        doc.close()
        new_doc.close()

        os.remove(original_pdf_path)
        os.rename(temp_filepath, original_pdf_path)

        # 操作後に履歴を保存
        _save_history()

        symbol_count = len(symbols)
        message = f'全ページに{symbol_count}箇所のシンボルマークを追加しました。'

        return _generate_thumbnails_and_response(message)

    except Exception as e:
        return jsonify({'error': f'シンボルマーク追加中にエラーが発生しました: {str(e)}'}), 500


@app.route('/preview_symbols', methods=['POST'])
def preview_symbols():
    """シンボルマークのプレビューを生成（PDFは変更しない）"""
    paths = get_session_paths()
    session_id = get_session_id()
    data = request.get_json()
    if not data or 'symbols' not in data:
        return jsonify({'error': 'シンボル設定が指定されていません'}), 400

    symbols = data['symbols']
    symbol_size = data.get('size', 14)
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    if not symbols:
        return jsonify({'error': '少なくとも1つのシンボルを選択してください'}), 400

    try:
        doc = fitz.open(original_pdf_path)
        preview_thumbnails = []

        # プレビュー用サムネイルフォルダを作成
        preview_folder = os.path.join(paths['thumbnail'], 'preview')
        if os.path.exists(preview_folder):
            shutil.rmtree(preview_folder)
        os.makedirs(preview_folder)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            rect = page.rect

            # ページを一時的にコピーしてシンボルを追加
            temp_doc = fitz.open()
            temp_page = temp_doc.new_page(width=rect.width, height=rect.height)
            temp_page.show_pdf_page(temp_page.rect, doc, page_num)

            # 各コーナーにシンボルを追加
            for corner, settings in symbols.items():
                symbol = settings['symbol']
                x_offset = settings['x']
                y_offset = settings['y']

                # コーナーに応じて中心位置を計算
                if corner == 'topleft':
                    center_x = x_offset
                    center_y = y_offset
                elif corner == 'topright':
                    center_x = rect.width - x_offset
                    center_y = y_offset
                elif corner == 'bottomleft':
                    center_x = x_offset
                    center_y = rect.height - y_offset
                elif corner == 'bottomright':
                    center_x = rect.width - x_offset
                    center_y = rect.height - y_offset
                else:
                    continue

                # シンボルを図形として描画
                _draw_symbol(temp_page, symbol, center_x, center_y, symbol_size)

            # サムネイルを生成
            pix = temp_page.get_pixmap(dpi=72)
            thumb_path = os.path.join(preview_folder, f'preview_{page_num}.png')
            pix.save(thumb_path)
            mtime = os.path.getmtime(thumb_path)
            preview_thumbnails.append(f'/thumbnails/{session_id}/preview/preview_{page_num}.png?t={mtime}')

            temp_doc.close()

        doc.close()

        return jsonify({
            'preview_thumbnails': preview_thumbnails,
            'message': 'プレビューを生成しました'
        })

    except Exception as e:
        return jsonify({'error': f'プレビュー生成中にエラーが発生しました: {str(e)}'}), 500


@app.route('/undo', methods=['POST'])
def undo():
    """一つ前の状態に戻す"""
    paths = get_session_paths()
    data = get_session_data()

    # history_index は現在の状態を指している
    # 一つ前に戻すには history_index - 1 の状態を復元する
    if data['history_index'] < 1:
        return jsonify({'error': 'これ以上戻せません'}), 400

    try:
        # 一つ前の履歴を取得
        data['history_index'] -= 1
        history_filename = data['history_stack'][data['history_index']]
        history_path = os.path.join(paths['history'], history_filename)


        if not os.path.exists(history_path):
            return jsonify({'error': '履歴ファイルが見つかりません'}), 400

        # PDFを復元
        original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
        shutil.copy(history_path, original_pdf_path)

        return _generate_thumbnails_and_response('1つ前の状態に戻しました')

    except Exception as e:
        return jsonify({'error': f'元に戻す処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/redo', methods=['POST'])
def redo():
    """一つ先の状態に進む"""
    paths = get_session_paths()
    data = get_session_data()

    if data['history_index'] >= len(data['history_stack']) - 1:
        return jsonify({'error': 'これ以上進めません'}), 400

    try:
        # 一つ先の履歴を取得
        data['history_index'] += 1
        history_filename = data['history_stack'][data['history_index']]
        history_path = os.path.join(paths['history'], history_filename)

        if not os.path.exists(history_path):
            return jsonify({'error': '履歴ファイルが見つかりません'}), 400

        # PDFを復元
        original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
        shutil.copy(history_path, original_pdf_path)

        return _generate_thumbnails_and_response('1つ先の状態に進みました')

    except Exception as e:
        return jsonify({'error': f'やり直す処理中にエラーが発生しました: {str(e)}'}), 500

@app.route('/history_status', methods=['GET'])
def history_status():
    """Undo/Redoが可能かどうかを返す"""
    data = get_session_data()
    can_undo = data['history_index'] >= 1
    can_redo = data['history_index'] < len(data['history_stack']) - 1
    return jsonify({'can_undo': can_undo, 'can_redo': can_redo})

@app.route('/get_original_filename', methods=['GET'])
def get_original_filename():
    """最初にアップロードされたファイル名を返す"""
    data = get_session_data()
    return jsonify({'filename': data['original_filename'] or 'edited'})

@app.route('/split_to_files', methods=['POST'])
def split_to_files():
    """各ページを個別のPDFファイルとして保存し、ZIPでダウンロード"""
    paths = get_session_paths()
    session_id = get_session_id()
    session_data_local = get_session_data()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    convert_to_image = data.get('convert_to_image', False)
    dpi = data.get('dpi', 150)

    try:
        # ベースファイル名を取得
        base_filename = session_data_local['original_filename'] or 'page'

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
        zip_path = os.path.join(paths['output'], zip_filename)

        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.getvalue())

        return jsonify({
            'message': message,
            'download_url': f'/download/{session_id}/{zip_filename}',
            'filename': zip_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'ページ分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/convert_to_image_pdf', methods=['POST'])
def convert_to_image_pdf():
    """PDFを画像ベースのPDFに変換（フォント問題を回避）"""
    paths = get_session_paths()
    session_id = get_session_id()
    session_data_local = get_session_data()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    dpi = data.get('dpi', 150)  # デフォルトは150 DPI
    custom_filename = data.get('filename', session_data_local['original_filename'] or 'image_pdf')

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
        output_path = os.path.join(paths['output'], output_filename)

        # 新しいPDFを保存
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)

        doc.close()
        new_doc.close()

        return jsonify({
            'message': f'{page_count}ページを画像PDFに変換しました（{dpi} DPI）',
            'download_url': f'/download/{session_id}/{output_filename}',
            'filename': output_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'画像PDF変換中にエラーが発生しました: {str(e)}'}), 500

@app.route('/convert_to_grayscale', methods=['POST'])
def convert_to_grayscale():
    """PDFを白黒（グレースケール）PDFに変換"""
    paths = get_session_paths()
    session_id = get_session_id()
    session_data_local = get_session_data()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    custom_filename = data.get('filename', session_data_local['original_filename'] or 'grayscale')

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

            # 新しいページを作成してコピー
            rect = page.rect
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num)

            # グレースケールに変換
            # すべての描画オブジェクトをグレースケールに変換
            pix = new_page.get_pixmap(colorspace=fitz.csGRAY)
            new_page.clean_contents()

            # ページをクリアして再描画
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            img_bytes = pix.tobytes("png")
            new_page.insert_image(new_page.rect, stream=img_bytes)

        # 出力ファイル名を準備
        if custom_filename.lower().endswith('.pdf'):
            custom_filename = custom_filename[:-4]
        output_filename = f'{custom_filename}_grayscale.pdf'
        output_path = os.path.join(paths['output'], output_filename)

        # 新しいPDFを保存
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)

        doc.close()
        new_doc.close()

        return jsonify({
            'message': f'{page_count}ページを白黒PDFに変換しました',
            'download_url': f'/download/{session_id}/{output_filename}',
            'filename': output_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'白黒PDF変換中にエラーが発生しました: {str(e)}'}), 500

@app.route('/convert_to_grayscale_image', methods=['POST'])
def convert_to_grayscale_image():
    """PDFを白黒（グレースケール）画像PDFに変換"""
    paths = get_session_paths()
    session_id = get_session_id()
    session_data_local = get_session_data()
    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')

    if not os.path.exists(original_pdf_path):
        return jsonify({'error': 'PDFファイルがアップロードされていません'}), 400

    data = request.get_json(silent=True) or {}
    dpi = data.get('dpi', 150)  # デフォルトは150 DPI
    custom_filename = data.get('filename', session_data_local['original_filename'] or 'grayscale_image')

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

            # ページをグレースケールで画像としてレンダリング
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)

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
        output_filename = f'{custom_filename}_grayscale_image.pdf'
        output_path = os.path.join(paths['output'], output_filename)

        # 新しいPDFを保存
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)

        doc.close()
        new_doc.close()

        return jsonify({
            'message': f'{page_count}ページを白黒画像PDFに変換しました（{dpi} DPI）',
            'download_url': f'/download/{session_id}/{output_filename}',
            'filename': output_filename,
            'page_count': page_count
        })

    except Exception as e:
        return jsonify({'error': f'白黒画像PDF変換中にエラーが発生しました: {str(e)}'}), 500

@app.route('/split_and_save', methods=['POST'])
def split_and_save():
    """分割線で区切られた各パートに名前を付けて保存"""
    paths = get_session_paths()
    session_id = get_session_id()

    original_pdf_path = os.path.join(paths['upload'], 'uploaded.pdf')
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
            output_path = os.path.join(paths['output'], filename)
            with open(output_path, 'wb') as f:
                writer.write(f)

            download_urls.append({
                'url': f'/download/{session_id}/{filename}',
                'filename': filename
            })

        return jsonify({
            'message': f'{len(parts_to_save)}個のファイルに分割しました',
            'files': download_urls
        })

    except Exception as e:
        return jsonify({'error': f'ファイル分割中にエラーが発生しました: {str(e)}'}), 500

@app.route('/thumbnails/<session_id>/<path:filename>')
def serve_thumbnail(session_id, filename):
    thumbnail_folder = os.path.join(BASE_THUMBNAIL_FOLDER, session_id)
    return send_from_directory(thumbnail_folder, filename)

@app.route('/download/<session_id>/<path:filename>')
def serve_output(session_id, filename):
    output_folder = os.path.join(BASE_OUTPUT_FOLDER, session_id)
    return send_from_directory(output_folder, filename, as_attachment=True)


# --- 更新チェック関連 ---
@app.route('/check_update', methods=['GET'])
def check_update():
    """更新をチェック"""
    # 本番環境（PythonAnywhere）では無効化
    if os.environ.get('FLASK_ENV') == 'production':
        return jsonify({'update_available': False, 'message': 'オンライン版では自動更新は無効です'})

    try:
        from updater import check_for_updates
        result = check_for_updates()
        return jsonify(result)
    except ImportError:
        return jsonify({'error': 'updater.pyが見つかりません'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/perform_update', methods=['POST'])
def perform_update_route():
    """更新を実行"""
    # 本番環境（PythonAnywhere）では無効化
    if os.environ.get('FLASK_ENV') == 'production':
        return jsonify({'success': False, 'message': 'オンライン版では自動更新は無効です'})

    try:
        from updater import check_for_updates, perform_update

        # まず更新チェック
        update_info = check_for_updates()
        if not update_info['update_available']:
            return jsonify({'success': False, 'message': '更新はありません'})

        if not update_info['download_url']:
            return jsonify({'success': False, 'message': 'ダウンロードURLが見つかりません'})

        # 更新を実行
        result = perform_update(update_info['download_url'])
        return jsonify(result)

    except ImportError:
        return jsonify({'success': False, 'message': 'updater.pyが見つかりません'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/get_version', methods=['GET'])
def get_version():
    """現在のバージョンを取得"""
    try:
        from updater import get_current_version
        return jsonify({'version': get_current_version()})
    except ImportError:
        # updater.pyがない場合はversion.txtを直接読む
        version_file = os.path.join(os.path.dirname(__file__), 'version.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                return jsonify({'version': f.read().strip()})
        return jsonify({'version': 'unknown'})


if __name__ == '__main__':
    # 環境変数で本番環境かどうかを判定（PythonAnywhereではFLASK_ENV=productionを設定）
    is_production = os.environ.get('FLASK_ENV') == 'production'

    if not is_production:
        # ローカル環境では起動時に更新チェック
        print("=" * 60)
        print("アプリケーションを起動しています...")

        try:
            from updater import check_for_updates, get_current_version
            current_ver = get_current_version()
            print(f"現在のバージョン: {current_ver}")

            print("更新をチェック中...")
            update_info = check_for_updates()

            if update_info.get('error'):
                print(f"更新チェックをスキップ: {update_info['error']}")
            elif update_info.get('update_available'):
                print(f"")
                print(f"★ 新しいバージョンが利用可能です: {update_info['latest_version']}")
                print(f"  アプリ内の「更新」ボタンから更新できます")
                print(f"")
            else:
                print("お使いのバージョンは最新です")
        except ImportError:
            print("(更新チェック機能は利用できません)")
        except Exception as e:
            print(f"更新チェック中にエラー: {e}")

        print("")
        print("Webブラウザで http://127.0.0.1:5000 を開いてください")
        print("=" * 60)

    app.run(host='127.0.0.1', port=5000, debug=not is_production)
