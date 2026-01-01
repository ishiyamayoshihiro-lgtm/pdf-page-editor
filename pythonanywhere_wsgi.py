"""
PythonAnywhere WSGI設定ファイル

このファイルの内容を PythonAnywhere の WSGI configuration file にコピペしてください。
【重要】 'yourname' の部分を自分のPythonAnywhereユーザー名に置き換えてください。
"""

import sys
import os

# プロジェクトフォルダのパスを追加
# 【重要】 'yourname' を自分のPythonAnywhereユーザー名に変更してください
project_home = '/home/yourname/pdf-page-editor'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 仮想環境のパスを設定
# 【重要】 'yourname' を自分のPythonAnywhereユーザー名に変更してください
activate_this = '/home/yourname/pdf-page-editor/venv/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), {'__file__': activate_this})

# 環境変数を設定（本番環境モード）
os.environ['FLASK_ENV'] = 'production'

# Flaskアプリケーションをインポート
from app import app as application
