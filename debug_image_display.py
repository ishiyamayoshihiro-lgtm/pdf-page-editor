
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import fitz  # PyMuPDF
from PIL import Image, ImageTk

class DebugApp:
    def __init__(self, root):
        self.root = root
        self.root.title("画像表示 診断テスト")
        self.root.geometry("700x800")

        self.fitz_doc = None
        self.photo_ref = None  # ガベージコレクションを防ぐために参照を保持

        # --- ウィジェット ---
        self.btn = ttk.Button(self.root, text="PDFを選択して1ページ目を表示", command=self.show_first_page)
        self.btn.pack(pady=20)

        self.img_label = ttk.Label(self.root, text="ここに画像が表示されます")
        self.img_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def show_first_page(self):
        """PDFを選択し、最初のページをレンダリングしてラベルに表示する"""
        path = filedialog.askopenfilename(title="PDFを選択", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return

        try:
            # 既存のドキュメントを閉じる
            if self.fitz_doc:
                self.fitz_doc.close()

            # PDFを開く
            self.fitz_doc = fitz.open(path)
            if self.fitz_doc.page_count == 0:
                messagebox.showwarning("警告", "このPDFにはページがありません。")
                return

            # 1ページ目をレンダリング
            page = self.fitz_doc.load_page(0)
            pix = page.get_pixmap(dpi=150)  # 解像度を少し上げる
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # PhotoImageを作成し、参照を保持
            self.photo_ref = ImageTk.PhotoImage(img)

            # ラベルに画像を設定
            self.img_label.config(image=self.photo_ref, text="")  # テキストをクリア
            
            messagebox.showinfo("成功", f"1ページ目の画像（サイズ: {img.width}x{img.height}）を表示しようとしました。")

        except Exception as e:
            messagebox.showerror("エラー", f"処理中にエラーが発生しました: {e}")
            # エラーが発生した場合、ラベルをリセット
            self.img_label.config(image=None, text="エラーが発生しました")
            self.photo_ref = None


    def on_closing(self):
        """ウィンドウを閉じるときの処理"""
        if self.fitz_doc:
            self.fitz_doc.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DebugApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
