# PythonAnywhere デプロイ手順

このアプリをインターネット経由でどこからでもアクセスできるようにする手順です。

## 必要なもの

- メールアドレス（PythonAnywhereアカウント登録用）
- クレジットカード不要！

## 手順1: PythonAnywhereアカウント作成

1. [PythonAnywhere](https://www.pythonanywhere.com/) にアクセス
2. 右上の「Start running Python online in less than a minute!」をクリック
3. 「Beginner」プランの「Create a Beginner account」をクリック
4. 以下を入力：
   - Username（ユーザー名）：この名前がURLになります（例：`yourname.pythonanywhere.com`）
   - Email（メールアドレス）
   - Password（パスワード）
5. 「Register」をクリック
6. メールが届くので、確認リンクをクリックして認証完了

## 手順2: ファイルをアップロード

### 方法A: GitHubを使う場合（推奨）

すでにGitHubにリポジトリがある場合：

1. PythonAnywhereにログイン後、上部メニューの「Consoles」をクリック
2. 「Bash」をクリックして新しいコンソールを開く
3. 以下のコマンドを実行（GitHubのURLを自分のものに変更）：
   ```bash
   git clone https://github.com/ishiyamayoshihiro-lgtm/pdf-page-editor.git
   cd pdf-page-editor
   ```

### 方法B: 手動アップロード

GitHubを使わない場合：

1. 上部メニューの「Files」をクリック
2. 「Upload a file」をクリック
3. このフォルダ内の以下のファイルを順番にアップロード：
   - `app.py`
   - `requirements.txt`
   - `static/` フォルダ内のすべてのファイル
   - `templates/` フォルダ内のすべてのファイル

ディレクトリ構成は以下のようになります：
```
/home/あなたのユーザー名/pdf-page-editor/
├── app.py
├── requirements.txt
├── static/
│   ├── script.js
│   └── style.css
└── templates/
    └── index.html
```

## 手順3: 必要なパッケージをインストール

1. 「Consoles」→「Bash」でコンソールを開く（すでに開いている場合はそのまま）
2. プロジェクトフォルダに移動：
   ```bash
   cd pdf-page-editor
   ```
3. 仮想環境を作成：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. パッケージをインストール：
   ```bash
   pip install -r requirements.txt
   ```

## 手順4: Webアプリの設定

1. 上部メニューの「Web」をクリック
2. 「Add a new web app」をクリック
3. 「Next」をクリック
4. 「Manual configuration」を選択
5. 「Python 3.10」を選択（最新のPython 3.xを選択）
6. 「Next」をクリック

### WSGI設定ファイルの編集

1. Webページの「Code」セクションにある「WSGI configuration file」のリンク（例：`/var/www/yourname_pythonanywhere_com_wsgi.py`）をクリック
2. ファイルの内容をすべて削除して、以下の内容に置き換え（`yourname`の部分を自分のユーザー名に変更）：

```python
import sys
import os

# プロジェクトフォルダのパスを追加（ユーザー名を変更してください）
project_home = '/home/yourname/pdf-page-editor'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 仮想環境のパスを設定（ユーザー名を変更してください）
activate_this = '/home/yourname/pdf-page-editor/venv/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), {'__file__': activate_this})

# 環境変数を設定（本番環境モード）
os.environ['FLASK_ENV'] = 'production'

# Flaskアプリケーションをインポート
from app import app as application
```

3. 「Save」をクリック

### 仮想環境のパス設定

1. Webページの「Virtualenv」セクションで「Enter path to a virtualenv」をクリック
2. 以下のパスを入力（`yourname`を自分のユーザー名に変更）：
   ```
   /home/yourname/pdf-page-editor/venv
   ```
3. チェックマークをクリック

### 静的ファイルの設定

1. Webページの「Static files」セクションで「Enter URL」をクリック
2. 以下を入力：
   - URL: `/static/`
   - Directory: `/home/yourname/pdf-page-editor/static`（`yourname`を自分のユーザー名に変更）
3. チェックマークをクリック

## 手順5: アプリを起動

1. Webページの上部にある緑色の「Reload」ボタンをクリック
2. 「yourname.pythonanywhere.com」のリンクをクリック（または新しいタブで開く）
3. PDF編集アプリが表示されれば成功！

## トラブルシューティング

### エラーログの確認方法

1. 「Web」タブを開く
2. 「Log files」セクションの「Error log」をクリック
3. エラーメッセージを確認

### よくあるエラーと解決方法

**エラー: "ImportError: No module named 'flask'"**
- 原因: パッケージがインストールされていない
- 解決: 手順3の仮想環境作成とパッケージインストールを再度実行

**エラー: "ModuleNotFoundError: No module named 'app'"**
- 原因: WSGIファイルのパスが間違っている
- 解決: WSGIファイル内の`yourname`を自分のユーザー名に変更

**ページが表示されない**
- 原因: 静的ファイルのパスが間違っている
- 解決: 「Static files」の設定を確認し、パスに自分のユーザー名が含まれているか確認

### ファイルを更新した場合

1. 「Files」からファイルを編集、または「Bash」コンソールで`git pull`
2. 「Web」タブの「Reload」ボタンをクリック

## セキュリティに関する注意

このアプリは誰でもアクセスできる状態です。以下の点に注意してください：

1. **URLを共有しない**: `yourname.pythonanywhere.com`のURLを知っている人は誰でもアクセスできます
2. **個人情報を含むPDFをアップロードしない**: 他の人もアクセスできる可能性があります
3. **定期的にファイルを削除**: アップロードしたPDFは `uploads/` フォルダに残ります

### パスワード保護を追加したい場合

基本認証を追加する手順は別途ご相談ください。

## 制限事項（無料プラン）

- **CPU時間**: 1日あたり100秒まで
- **ディスク容量**: 512MBまで
- **Webアプリ**: 1つまで
- **スリープ**: 3ヶ月アクセスがないとアプリが停止（再起動は簡単）

個人利用であれば十分な制限です。

## サポート

デプロイで困ったことがあれば、エラーメッセージを確認して質問してください。
