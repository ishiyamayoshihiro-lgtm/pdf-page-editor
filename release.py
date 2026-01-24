#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
リリース自動化スクリプト
README.htmlの更新、バージョン更新、Git操作、GitHubリリース作成を自動化
"""

import os
import re
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'version.txt')
README_FILE = os.path.join(BASE_DIR, 'README.html')


def get_current_version():
    """現在のバージョンを取得"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return '0.0'


def update_version(new_version):
    """バージョンファイルを更新"""
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(new_version)
    print(f"  version.txt を {new_version} に更新しました")


def update_readme(new_version, changes):
    """README.htmlの更新履歴を更新"""
    with open(README_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    today = datetime.now().strftime('%Y-%m-%d')

    # 変更内容をHTMLリスト形式に変換
    changes_html = '\n'.join([f'<li>{change}</li>' for change in changes])

    # 新しい更新履歴エントリ
    new_entry = f'''<h2>更新履歴</h2>
<h3>{today} (v{new_version})</h3>
<ul>
{changes_html}
</ul>'''

    # 既存の更新履歴を置換
    content = re.sub(r'<h2>更新履歴</h2>', new_entry, content, count=1)

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  README.html に v{new_version} の更新履歴を追加しました")


def run_git_commands(new_version, changes):
    """Git操作を実行"""
    os.chdir(BASE_DIR)

    # ステージング
    subprocess.run(['git', 'add', 'version.txt', 'README.html'], check=True)

    # コミット
    commit_message = f"Release v{new_version}: {changes[0]}"
    subprocess.run(['git', 'commit', '-m', commit_message], check=True)
    print(f"  コミット完了")

    # タグ作成
    tag = f'v{new_version}'
    subprocess.run(['git', 'tag', tag], check=True)
    print(f"  タグ {tag} を作成しました")

    # プッシュ
    subprocess.run(['git', 'push', 'origin', 'master', '--tags'], check=True)
    print(f"  GitHubにプッシュしました")

    return tag


def create_github_release(tag, changes):
    """GitHubリリースを作成（gh CLIが必要）"""
    # リリースノートを作成
    notes = f"## PDF Page Editor {tag}\n\n"
    notes += "### 更新内容\n"
    for change in changes:
        notes += f"- {change}\n"

    # gh CLIのパスを探す
    gh_paths = [
        'gh',  # PATHにある場合
        r'C:\Program Files\GitHub CLI\gh.exe',
        r'C:\Program Files (x86)\GitHub CLI\gh.exe',
        os.path.expanduser(r'~\AppData\Local\Programs\GitHub CLI\gh.exe'),
    ]

    gh_cmd = None
    for path in gh_paths:
        try:
            result = subprocess.run([path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                gh_cmd = path
                break
        except FileNotFoundError:
            continue

    if not gh_cmd:
        print(f"\n  ⚠ gh CLIが見つかりません")
        print(f"  以下のURLからリリースを手動で作成してください:")
        print(f"  https://github.com/ishiyamayoshihiro-lgtm/pdf-page-editor/releases/new?tag={tag}")
        return False

    try:
        result = subprocess.run(
            [gh_cmd, 'release', 'create', tag, '--title', tag, '--notes', notes],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"  GitHubリリースを作成しました")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  リリース作成エラー: {e.stderr}")
        return False


def main():
    print("=" * 50)
    print("PDF Page Editor リリーススクリプト")
    print("=" * 50)

    current = get_current_version()
    print(f"\n現在のバージョン: {current}")

    # 新しいバージョンを入力
    new_version = input(f"新しいバージョンを入力 (例: 2.5): ").strip()
    if not new_version:
        print("キャンセルしました")
        return

    # 変更内容を入力
    print("\n変更内容を入力してください（空行で終了）:")
    changes = []
    while True:
        change = input("- ").strip()
        if not change:
            break
        changes.append(change)

    if not changes:
        print("変更内容がありません。キャンセルしました")
        return

    # 確認
    print(f"\n=== 確認 ===")
    print(f"バージョン: {current} → {new_version}")
    print(f"変更内容:")
    for c in changes:
        print(f"  - {c}")

    confirm = input("\nこの内容でリリースしますか？ (y/n): ").strip().lower()
    if confirm != 'y':
        print("キャンセルしました")
        return

    print("\n=== リリース処理を開始 ===")

    try:
        # 1. バージョン更新
        update_version(new_version)

        # 2. README更新
        update_readme(new_version, changes)

        # 3. Git操作
        tag = run_git_commands(new_version, changes)

        # 4. GitHubリリース作成
        create_github_release(tag, changes)

        print("\n=== リリース完了 ===")
        print(f"バージョン {new_version} をリリースしました！")

    except subprocess.CalledProcessError as e:
        print(f"\nエラーが発生しました: {e}")
        return
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        return


if __name__ == '__main__':
    main()
