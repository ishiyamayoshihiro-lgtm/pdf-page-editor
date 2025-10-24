# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PDF editing web application built with Flask that allows users to visually manipulate PDF files through a browser interface. The application provides a tabbed interface for uploading, splitting, deleting, rotating, and reordering PDF pages with real-time thumbnail previews.

## Running the Application

### Starting the development server

```bash
# Windows
python app.py
# or
py app.py

# Mac/Linux
python3 app.py
```

The application runs at `http://127.0.0.1:5000`

To stop the server, press `Ctrl+C` in the terminal.

### Installing dependencies

```bash
# Windows
pip install Flask PyMuPDF pypdf
# or
py -m pip install Flask PyMuPDF pypdf

# Mac/Linux
pip3 install Flask PyMuPDF pypdf
```

Dependencies:
- `Flask` - Web framework
- `PyMuPDF` (fitz) - PDF rendering and thumbnail generation
- `pypdf` - PDF manipulation (page operations)

## Architecture

### Backend Architecture (app.py)

The Flask application maintains a single shared PDF file (`uploaded.pdf`) that gets modified through various operations:

**Key Design Pattern**: All PDF operations follow a regeneration pattern where:
1. The original `uploaded.pdf` is read
2. Operations are performed on a temporary file
3. The original is deleted and replaced atomically
4. Thumbnails are regenerated to reflect changes

**Helper Functions**:
- `_regenerate_pdf_and_thumbnails()` - Core function that rebuilds the PDF based on a new page order
- `_generate_thumbnails_and_response()` - Creates PNG thumbnails at 72 DPI using PyMuPDF and returns JSON response

**File Storage Structure**:
- `uploads/` - Contains single `uploaded.pdf` (the working file)
- `thumbnails/` - PNG thumbnails named `page_{i}.png` with cache-busting timestamps
- `output/` - Generated PDFs available for download

### Frontend Architecture (static/script.js, templates/index.html)

**State Management**:
- `sharedPdfData` - Global state object containing `{page_count, thumbnails}` shared across all tabs
- Each tab maintains its own selection state arrays (e.g., `selectedPagesToDelete`, `clickedOrder`)

**Tab System**:
The UI has 6 tabs that all operate on the same underlying PDF:
1. Upload - Add up to 5 PDFs at once (pages concatenated in selection order) and clear all
2. Split - Divide landscape-oriented pages into left/right halves
3. Delete - Remove selected pages
4. Edit - Rotate pages 90° left/right, swap odd/even, reverse all
5. Reorder - Visual reordering using click-to-order (with circled numbers ①②③) or prev/next buttons
6. Save - Preview and download the final edited PDF

**Gallery Population Pattern**:
Each tab has its own `populateGallery*()` function that renders thumbnails and attaches tab-specific click handlers. When switching tabs, `loadDataToActiveTab()` re-renders the appropriate gallery with current state.

### PDF Processing Flow

**Split Operation** (app.py:146-196):
Uses PyMuPDF to detect landscape pages (`width > height`) and creates two new pages by clipping left and right halves using `show_pdf_page()` with custom rectangles.

**Delete/Reorder Operations** (app.py:198-279):
Use pypdf to rebuild the PDF by selecting pages in a specific order - deletion is implemented as reordering without the deleted pages.

**Rotate Operation** (app.py:208-239):
Uses pypdf's `page.rotate()` method which modifies page rotation metadata.

## Important Implementation Notes

### Atomic File Operations
When modifying `uploaded.pdf`, always use the temp file pattern:
```python
temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_temp.pdf')
# write to temp_filepath
os.remove(original_pdf_path)
os.rename(temp_filepath, original_pdf_path)
```

### Thumbnail Cache Busting
Thumbnails include timestamp query parameters (`?t={mtime}`) to force browser reload after operations that change page content.

### Dual PDF Library Usage
- **PyMuPDF (fitz)**: Used for rendering (thumbnails) and split operations requiring pixel-level manipulation
- **pypdf**: Used for page-level operations (delete, rotate, reorder, merge) due to simpler API

### Frontend State Synchronization
After any backend operation that modifies the PDF:
1. Backend returns new `page_count` and `thumbnails` array
2. Frontend updates `sharedPdfData`
3. `loadDataToActiveTab()` re-renders current tab's gallery
4. All selection states are cleared via `resetAllSelections()`

## Tab-Specific Behaviors

**Upload Tab**:
- Features 5 separate file input fields (templates/index.html:30-54) allowing batch file selection
- Each file input has an associated filename display area that shows the complete filename
- Filenames use ellipsis overflow with hover tooltips for long names (static/style.css:280-299)
- Selected files are uploaded sequentially in order (static/script.js:120-168)
- Multiple uploads append pages to the existing PDF
- The `/clear_all` endpoint is automatically called on page load to ensure a clean state

**Split Tab**: Only processes landscape-oriented pages (width > height). Can operate on selected pages or all pages. Generates a downloadable PDF (`split.pdf`) immediately, unlike other tabs that only update `uploaded.pdf`.

**Delete Tab**: Shows a red `×` overlay on hover. Selected pages are removed by rebuilding the PDF without those pages using `_regenerate_pdf_and_thumbnails()`.

**Edit Tab**:
- Rotation operations use pypdf's `page.rotate()` method
- Swap odd/even pairs consecutive pages (0↔1, 2↔3, etc.)
- Reverse all creates a completely reversed page order

**Reorder Tab**: Has two distinct interaction modes:
1. **Click-to-order mode**: `clickedOrder` array - assigns circled numbers (①②③...) to clicked pages
   - `getCircledNumber()` function (static/script.js:499-506) converts numbers 1-50 to Unicode circled digits
   - Numbers display via `.order-overlay` which becomes visible when `.ordered` class is applied
   - CSS updated (static/style.css:162-164) to show overlay for both `.selected` and `.ordered` classes
2. **Prev/Next mode**: `selectedPagesToMove` array - uses DOM manipulation to physically move selected elements

**Save Tab**: Read-only gallery that uses the `/reorder` endpoint to generate the final `reordered.pdf` and triggers automatic download.

## Common Development Patterns

When adding new PDF operations:
1. Create route in app.py that calls `_regenerate_pdf_and_thumbnails()` with new page order
2. Return JSON with `message`, `page_count`, `thumbnails`, and optionally `download_url`
3. Frontend calls `performManipulation()` helper which handles common loading states and UI updates
4. Add button/controls in appropriate tab in index.html
5. Wire up event listener in script.js
