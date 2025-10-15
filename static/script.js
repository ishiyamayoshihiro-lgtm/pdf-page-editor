
document.addEventListener('DOMContentLoaded', () => {
    const pdfFileInput = document.getElementById('pdf-file-input');
    const uploadButton = document.getElementById('upload-button');
    const gallery = document.getElementById('gallery');
    const status = document.getElementById('status');
    const applyOrderButton = document.getElementById('apply-order-button');
    const clearSelectionButton = document.getElementById('clear-selection-button');
    const saveButton = document.getElementById('save-button');
    const downloadLink = document.getElementById('download-link');
    const sizeSlider = document.getElementById('size-slider');

    // --- スライダーのイベントリスナー ---
    sizeSlider.addEventListener('input', (e) => {
        document.documentElement.style.setProperty('--thumbnail-width', `${e.target.value}px`);
    });

    let clickedOrder = [];
    let pageCount = 0;

    // --- 1. アップロード処理 ---
    uploadButton.addEventListener('click', async () => {
        const file = pdfFileInput.files[0];
        if (!file) {
            status.textContent = 'ファイルが選択されていません。';
            return;
        }

        const formData = new FormData();
        formData.append('pdfFile', file);

        resetState();
        status.textContent = 'アップロード中... サムネイルを生成しています。これには時間がかかる場合があります。';
        setButtonsState(false);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'サーバーエラー');
            }

            pageCount = data.page_count;
            populateGallery(data.thumbnails);
            status.textContent = `サムネイルの準備ができました。 (${pageCount}ページ)`;
            setButtonsState(true, false);

        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            setButtonsState(false);
        }
    });

    // --- 2. ギャラリーの操作 ---
    function populateGallery(thumbnails) {
        gallery.innerHTML = '';
        thumbnails.forEach((thumbUrl, index) => {
            const pageContainer = document.createElement('div');
            pageContainer.className = 'page-container';
            pageContainer.dataset.originalIndex = index;

            const img = document.createElement('img');
            img.src = thumbUrl + '?t=' + new Date().getTime(); // キャッシュを回避

            const pageNum = document.createElement('div');
            pageNum.className = 'page-number';
            pageNum.textContent = `ページ ${index + 1}`;

            const orderOverlay = document.createElement('div');
            orderOverlay.className = 'order-overlay';

            pageContainer.appendChild(img);
            pageContainer.appendChild(pageNum);
            pageContainer.appendChild(orderOverlay);

            pageContainer.addEventListener('click', () => onPreviewClick(pageContainer));
            
            gallery.appendChild(pageContainer);
        });
    }

    function onPreviewClick(pageContainer) {
        const originalIndex = parseInt(pageContainer.dataset.originalIndex, 10);

        const foundIndex = clickedOrder.indexOf(originalIndex);
        if (foundIndex > -1) {
            // すでに選択されている場合は解除
            clickedOrder.splice(foundIndex, 1);
        } else {
            // 新しく選択
            clickedOrder.push(originalIndex);
        }
        updateGalleryOverlays();
    }

    function updateGalleryOverlays() {
        document.querySelectorAll('.page-container').forEach(container => {
            const originalIndex = parseInt(container.dataset.originalIndex, 10);
            const orderIndex = clickedOrder.indexOf(originalIndex);

            if (orderIndex > -1) {
                container.classList.add('selected');
                container.querySelector('.order-overlay').textContent = orderIndex + 1;
            } else {
                container.classList.remove('selected');
            }
        });
    }

    // --- 3. 並べ替えと保存 ---
    clearSelectionButton.addEventListener('click', () => {
        clickedOrder = [];
        updateGalleryOverlays();
    });

    applyOrderButton.addEventListener('click', () => {
        if (clickedOrder.length === 0) return;

        const remainingPages = [];
        for (let i = 0; i < pageCount; i++) {
            if (!clickedOrder.includes(i)) {
                remainingPages.push(i);
            }
        }

        const newPageOrder = clickedOrder.concat(remainingPages);
        const newThumbnails = newPageOrder.map(index => `/thumbnails/page_${index}.png`);
        
        populateGallery(newThumbnails);
        clickedOrder = [];
        status.textContent = 'ページの並べ替えを適用しました。';
    });

    saveButton.addEventListener('click', async () => {
        const pageContainers = Array.from(gallery.querySelectorAll('.page-container'));
        const finalOrder = pageContainers.map(c => parseInt(c.dataset.originalIndex, 10));

        if (finalOrder.length !== pageCount) {
            status.textContent = 'ページの数が一致しません。エラーが発生しました。';
            return;
        }

        status.textContent = 'PDFを生成中...';
        setButtonsState(false);

        try {
            const response = await fetch('/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ order: finalOrder })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'サーバーエラー');
            }

            downloadLink.href = data.download_url;
            downloadLink.style.display = 'block';
            status.textContent = 'PDFの準備ができました！リンクをクリックしてダウンロードしてください。';
            setButtonsState(true, true);

        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            setButtonsState(true, false);
        }
    });

    // --- ヘルパー関数 ---
    function resetState() {
        gallery.innerHTML = '';
        status.textContent = '';
        downloadLink.style.display = 'none';
        clickedOrder = [];
        pageCount = 0;
    }

    function setButtonsState(enabled, saveEnabled = enabled) {
        uploadButton.disabled = !enabled;
        applyOrderButton.disabled = !enabled;
        clearSelectionButton.disabled = !enabled;
        saveButton.disabled = !saveEnabled;
    }
});
