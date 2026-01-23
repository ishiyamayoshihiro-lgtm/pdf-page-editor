#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自動更新モジュール
GitHubリリースから最新バージョンをチェックし、更新を行う
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# GitHubリポジトリ情報
GITHUB_OWNER = "ishiyamayoshihiro-lgtm"
GITHUB_REPO = "pdf-page-editor"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# アプリケーションのベースディレクトリ
BASE_DIR = Path(__file__).parent.absolute()
VERSION_FILE = BASE_DIR / "version.txt"


def get_current_version():
    """現在のバージョンを取得"""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding='utf-8').strip()
        return "0.0.0"
    except Exception:
        return "0.0.0"


def parse_version(version_str):
    """バージョン文字列をタプルに変換（比較用）"""
    # "v1.2.3" -> (1, 2, 3)
    version_str = version_str.lstrip('v').strip()
    try:
        parts = version_str.split('.')
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_for_updates():
    """
    GitHubリリースから最新バージョンをチェック

    Returns:
        dict: 更新情報 {
            'update_available': bool,
            'current_version': str,
            'latest_version': str,
            'download_url': str or None,
            'release_notes': str or None,
            'error': str or None
        }
    """
    current_version = get_current_version()
    result = {
        'update_available': False,
        'current_version': current_version,
        'latest_version': current_version,
        'download_url': None,
        'release_notes': None,
        'error': None
    }

    try:
        # GitHub APIにリクエスト
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={'User-Agent': 'PDF-Page-Editor-Updater'}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        latest_version = data.get('tag_name', '').lstrip('v')
        result['latest_version'] = latest_version
        result['release_notes'] = data.get('body', '')

        # ZIPアセットを探す
        assets = data.get('assets', [])
        for asset in assets:
            if asset['name'].endswith('.zip'):
                result['download_url'] = asset['browser_download_url']
                break

        # ZIPアセットがない場合はソースコードのZIPを使用
        if not result['download_url']:
            result['download_url'] = data.get('zipball_url')

        # バージョン比較
        current_tuple = parse_version(current_version)
        latest_tuple = parse_version(latest_version)

        if latest_tuple > current_tuple:
            result['update_available'] = True

    except urllib.error.URLError as e:
        result['error'] = f"ネットワークエラー: {str(e)}"
    except json.JSONDecodeError:
        result['error'] = "リリース情報の解析に失敗しました"
    except Exception as e:
        result['error'] = f"更新チェック中にエラーが発生しました: {str(e)}"

    return result


def download_and_extract(download_url, target_dir=None):
    """
    ZIPファイルをダウンロードして展開

    Args:
        download_url: ダウンロードURL
        target_dir: 展開先ディレクトリ（Noneの場合は一時ディレクトリ）

    Returns:
        Path: 展開されたディレクトリのパス
    """
    if target_dir is None:
        target_dir = Path(tempfile.mkdtemp())
    else:
        target_dir = Path(target_dir)

    # ZIPファイルをダウンロード
    zip_path = target_dir / "update.zip"

    req = urllib.request.Request(
        download_url,
        headers={'User-Agent': 'PDF-Page-Editor-Updater'}
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        with open(zip_path, 'wb') as f:
            f.write(response.read())

    # ZIPを展開
    extract_dir = target_dir / "extracted"
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # ZIPファイルを削除
    zip_path.unlink()

    # 展開されたディレクトリを返す（GitHubのzipballは1階層深い）
    subdirs = list(extract_dir.iterdir())
    if len(subdirs) == 1 and subdirs[0].is_dir():
        return subdirs[0]
    return extract_dir


def perform_update(download_url, callback=None):
    """
    更新を実行

    Args:
        download_url: ダウンロードURL
        callback: 進捗コールバック関数 callback(message, progress)

    Returns:
        dict: 結果 {'success': bool, 'message': str}
    """
    def notify(message, progress=None):
        if callback:
            callback(message, progress)
        print(message)

    try:
        notify("更新をダウンロード中...", 10)

        # 一時ディレクトリにダウンロード＆展開
        temp_dir = Path(tempfile.mkdtemp())
        extracted_dir = download_and_extract(download_url, temp_dir)

        notify("ファイルを更新中...", 50)

        # 更新対象のファイル（設定ファイルなどは除外）
        update_files = [
            'app.py',
            'updater.py',
            'version.txt',
            'templates',
            'static',
        ]

        # バックアップ用ディレクトリ
        backup_dir = BASE_DIR / "_backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        backup_dir.mkdir()

        # ファイルを更新
        for item_name in update_files:
            src = extracted_dir / item_name
            dst = BASE_DIR / item_name

            if not src.exists():
                continue

            # バックアップ
            if dst.exists():
                backup_dst = backup_dir / item_name
                if dst.is_dir():
                    shutil.copytree(dst, backup_dst)
                else:
                    shutil.copy2(dst, backup_dst)

            # 更新
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()

            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        notify("クリーンアップ中...", 90)

        # 一時ファイルを削除
        shutil.rmtree(temp_dir, ignore_errors=True)

        notify("更新完了！", 100)

        return {
            'success': True,
            'message': '更新が完了しました。アプリケーションを再起動してください。'
        }

    except Exception as e:
        return {
            'success': False,
            'message': f'更新中にエラーが発生しました: {str(e)}'
        }


def restart_application():
    """アプリケーションを再起動"""
    python = sys.executable
    script = str(BASE_DIR / "app.py")

    # 新しいプロセスを起動
    if sys.platform == 'win32':
        subprocess.Popen([python, script], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([python, script])

    # 現在のプロセスを終了
    sys.exit(0)


# コマンドラインから実行された場合
if __name__ == "__main__":
    print("=== PDF Page Editor 更新チェック ===")
    print(f"現在のバージョン: {get_current_version()}")
    print("")

    result = check_for_updates()

    if result['error']:
        print(f"エラー: {result['error']}")
    elif result['update_available']:
        print(f"新しいバージョンが利用可能です: {result['latest_version']}")
        print(f"ダウンロードURL: {result['download_url']}")
        if result['release_notes']:
            print(f"\nリリースノート:\n{result['release_notes']}")

        answer = input("\n更新しますか？ (y/n): ")
        if answer.lower() == 'y':
            update_result = perform_update(result['download_url'])
            print(update_result['message'])
            if update_result['success']:
                answer = input("再起動しますか？ (y/n): ")
                if answer.lower() == 'y':
                    restart_application()
    else:
        print("お使いのバージョンは最新です。")
