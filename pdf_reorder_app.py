
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pypdf
import os
import fitz  # PyMuPDF
from PIL import Image, ImageTk

# 標準のtkウィジェットを使用したスクロール可能なフレーム
class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas) # ttk.Frame -> tk.Frame

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

class PDFReorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDFページ並べ替えツール (ギャラリービュー)")
        self.root.geometry("900x700")
        self.root.minsize(600, 400)

        # --- 状態変数 ---
        self.pdf_path = None
        self.pdf_reader = None
        self.fitz_doc = None
        self.page_order = []
        self.clicked_order = []
        self.preview_widgets = {}
        self.thumbnail_images = {}
        self.is_loading = False

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.is_loading = False
        if self.fitz_doc:
            self.fitz_doc.close()
        self.root.destroy()

    def _create_widgets(self):
        # 上部とコントロール部分はモダンなttkウィジェットを維持
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X, side=tk.TOP)

        self.select_button = ttk.Button(top_frame, text="PDFを選択", command=self.select_pdf)
        self.select_button.pack(side=tk.LEFT, padx=(0, 10))

        self.file_label = ttk.Label(top_frame, text="PDFが選択されていません", anchor=tk.W)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.save_button = ttk.Button(top_frame, text="名前を付けて保存...", command=self.save_pdf)
        self.save_button.pack(side=tk.RIGHT, padx=(10, 0))

        controls_frame = ttk.Frame(self.root, padding="10")
        controls_frame.pack(fill=tk.X, side=tk.TOP)

        self.apply_button = ttk.Button(controls_frame, text="並べ替えを適用", command=self.apply_click_order)
        self.apply_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.clear_button = ttk.Button(controls_frame, text="選択をクリア", command=self.clear_click_order)
        self.clear_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.progress_label = ttk.Label(self.root, text="", anchor=tk.CENTER)
        self.progress_label.pack(fill=tk.X, padx=10)

        # ギャラリー部分は標準のtkウィジェットを使用
        gallery_container = tk.Frame(self.root, padx=10, pady=10)
        gallery_container.pack(fill=tk.BOTH, expand=True)
        self.scrollable_gallery = ScrollableFrame(gallery_container)

    def clear_resources(self):
        self.is_loading = False
        self.pdf_path = None
        self.pdf_reader = None
        if self.fitz_doc:
            self.fitz_doc.close()
            self.fitz_doc = None
        self.page_order = []
        self.clicked_order = []
        self.thumbnail_images.clear()
        self.preview_widgets.clear()
        self.file_label.config(text="PDFが選択されていません")
        for widget in self.scrollable_gallery.scrollable_frame.winfo_children():
            widget.destroy()

    def select_pdf(self):
        if self.is_loading: return
        path = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDF files", "*.pdf")])
        if not path: return

        self.clear_resources()

        try:
            self.pdf_reader = pypdf.PdfReader(path)
            self.fitz_doc = fitz.open(path)
            self.pdf_path = path
            self.page_order = list(range(len(self.pdf_reader.pages)))
            self.file_label.config(text=os.path.basename(path))
            self.start_populate_gallery()
        except Exception as e:
            messagebox.showerror("エラー", f"PDFファイルの読み込みに失敗しました。\n{e}")
            self.clear_resources()

    def start_populate_gallery(self):
        if self.is_loading: return
        self.is_loading = True
        self.set_ui_state(tk.DISABLED)

        for widget in self.scrollable_gallery.scrollable_frame.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()
        self.thumbnail_images.clear()

        if not self.fitz_doc: 
            self.is_loading = False
            self.set_ui_state(tk.NORMAL)
            return

        self.root.after(10, self.process_next_page, 0)

    def process_next_page(self, page_index):
        if not self.is_loading or page_index >= len(self.page_order):
            self.progress_label.config(text="")
            self.is_loading = False
            self.set_ui_state(tk.NORMAL)
            return

        total_pages = len(self.page_order)
        self.progress_label.config(text=f"サムネイル読み込み中... {page_index + 1}/{total_pages}")

        cols = max(1, self.scrollable_gallery.winfo_width() // 180)
        row, col = divmod(page_index, cols)
        original_index = self.page_order[page_index]

        # --- 標準tkウィジェットを使用 ---
        page_frame = tk.Frame(self.scrollable_gallery.scrollable_frame, relief=tk.RAISED, borderwidth=2, padx=5, pady=5)
        page_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        img_label = self.create_thumbnail(page_frame, original_index)
        if img_label:
            img_label.pack()

        num_label = tk.Label(page_frame, text=f"ページ {original_index + 1}")
        num_label.pack()

        order_label = tk.Label(page_frame, text="", font=("Arial", 16, "bold"), fg="white", bg="#c00000")
        # --- ここまで ---
        
        click_handler = lambda event, index=original_index: self.on_preview_click(index)
        page_frame.bind("<Button-1>", click_handler)
        if img_label: img_label.bind("<Button-1>", click_handler)
        num_label.bind("<Button-1>", click_handler)

        self.preview_widgets[original_index] = {"frame": page_frame, "order_label": order_label}
        
        self.root.after(1, self.process_next_page, page_index + 1)

    def create_thumbnail(self, parent, page_index):
        try:
            page = self.fitz_doc.load_page(page_index)
            THUMBNAIL_HEIGHT = 200
            pix = page.get_pixmap(dpi=72)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ratio = THUMBNAIL_HEIGHT / img.height
            new_width = int(img.width * ratio)
            resized_img = img.resize((new_width, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
            photo_img = ImageTk.PhotoImage(resized_img)
            self.thumbnail_images[page_index] = photo_img
            # --- 標準tkウィジェットを使用 ---
            return tk.Label(parent, image=photo_img)
        except Exception as e:
            print(f"Error creating thumbnail for page {page_index}: {e}")
            return None

    def on_preview_click(self, original_index):
        if self.is_loading: return
        if original_index in self.clicked_order:
            self.clicked_order.remove(original_index)
        else:
            self.clicked_order.append(original_index)
        self.update_gallery_overlays()

    def update_gallery_overlays(self):
        for original_index, widgets in self.preview_widgets.items():
            if original_index in self.clicked_order:
                click_num = self.clicked_order.index(original_index) + 1
                widgets["order_label"].config(text=f" {click_num} ")
                widgets["order_label"].place(relx=0.0, rely=0.0, anchor=tk.NW)
                widgets["frame"].config(relief=tk.SUNKEN, borderwidth=3)
            else:
                widgets["order_label"].config(text="")
                widgets["order_label"].place_forget()
                widgets["frame"].config(relief=tk.RAISED, borderwidth=2)

    def apply_click_order(self):
        if self.is_loading or not self.clicked_order: return
        remaining_pages = [p for p in self.page_order if p not in self.clicked_order]
        self.page_order = self.clicked_order + remaining_pages
        self.clear_click_order()
        self.start_populate_gallery()
        messagebox.showinfo("成功", "ページの並べ替えを適用しました。")

    def clear_click_order(self):
        if self.is_loading: return
        self.clicked_order.clear()
        if self.preview_widgets:
            self.update_gallery_overlays()

    def save_pdf(self):
        if self.is_loading or not self.pdf_reader: 
            messagebox.showwarning("警告", "PDFファイルが選択されていません。")
            return

        save_path = filedialog.asksaveasfilename(
            title="名前を付けて保存", filetypes=[("PDF files", "*.pdf")],
            defaultextension=".pdf",
            initialfile=f"{os.path.splitext(os.path.basename(self.pdf_path))[0]}_reordered.pdf"
        )
        if not save_path: return

        try:
            writer = pypdf.PdfWriter()
            for original_index in self.page_order:
                writer.add_page(self.pdf_reader.pages[original_index])
            with open(save_path, "wb") as f:
                writer.write(f)
            messagebox.showinfo("成功", f"PDFを保存しました:\n{save_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"PDFの保存中にエラーが発生しました。\n{e}")

    def set_ui_state(self, state):
        self.select_button.config(state=state)
        self.save_button.config(state=state)
        self.apply_button.config(state=state)
        self.clear_button.config(state=state)

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFReorderApp(root)
    root.mainloop()
