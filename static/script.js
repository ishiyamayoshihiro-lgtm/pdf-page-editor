document.addEventListener('DOMContentLoaded', () => {
    // ========================================
    // グローバル変数・定数
    // ========================================
    let sharedPdfData = null;
    let galleriesPopulated = {
        upload: false,
        split: false,
        delete: false,
        edit: false,
        reorder: false,
        mask: false,
        save: false
    };

    // --- 共通要素 ---
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const placeholders = document.querySelectorAll('.placeholder');
    const status = document.getElementById('status');
    const undoButton = document.getElementById('undo-button');
    const redoButton = document.getElementById('redo-button');

    // --- アップロードタブ要素 ---
    const pdfFileInputs = [
        document.getElementById('pdf-file-input-1'),
        document.getElementById('pdf-file-input-2'),
        document.getElementById('pdf-file-input-3'),
        document.getElementById('pdf-file-input-4'),
        document.getElementById('pdf-file-input-5')
    ];
    const filenameDisplays = [
        document.getElementById('filename-display-1'),
        document.getElementById('filename-display-2'),
        document.getElementById('filename-display-3'),
        document.getElementById('filename-display-4'),
        document.getElementById('filename-display-5')
    ];
    const uploadButton = document.getElementById('upload-button');
    const clearAllButton = document.getElementById('clear-all-button');
    const galleryUpload = document.getElementById('gallery-upload');

    // --- ページ分割タブ要素 ---
    const gallerySplit = document.getElementById('gallery-split');
    const splitSelectedButton = document.getElementById('split-selected-button');
    const splitAllButton = document.getElementById('split-all-button');
    const clearSelectionButtonSplit = document.getElementById('clear-selection-button-split');
    const sizeSliderSplit = document.getElementById('size-slider-split');
    let selectedPagesToSplit = [];

    // --- ページ削除タブ要素 ---
    const galleryDelete = document.getElementById('gallery-delete');
    const deleteButton = document.getElementById('delete-button');
    const clearSelectionButtonDelete = document.getElementById('clear-selection-button-delete');
    const sizeSliderDelete = document.getElementById('size-slider-delete');
    let selectedPagesToDelete = [];

    // --- ページ編集タブ要素 ---
    const galleryEdit = document.getElementById('gallery-edit');
    const rotateLeftButton = document.getElementById('rotate-left-button');
    const rotateRightButton = document.getElementById('rotate-right-button');
    const clearSelectionButtonEdit = document.getElementById('clear-selection-button-edit');
    const swapOddEvenButton = document.getElementById('swap-odd-even-button');
    const reverseAllButton = document.getElementById('reverse-all-button');
    const sizeSliderEdit = document.getElementById('size-slider-edit');
    let selectedPagesToEdit = [];

    // --- ページ並べ替えタブ要素 ---
    const galleryReorder = document.getElementById('gallery-reorder');
    const applyOrderButton = document.getElementById('apply-order-button');
    const clearSelectionButton = document.getElementById('clear-selection-button');
    const movePrevButton = document.getElementById('move-prev-button');
    const moveNextButton = document.getElementById('move-next-button');
    const sizeSliderReorder = document.getElementById('size-slider-reorder');
    let clickedOrder = [];
    let selectedPagesToMove = [];

    // --- マスキングタブ要素 ---
    const maskCanvas = document.getElementById('mask-canvas');
    const maskCanvasContainer = document.getElementById('mask-canvas-container');
    const galleryMask = document.getElementById('gallery-mask');
    const applyMaskButton = document.getElementById('apply-mask-button');
    const clearMaskButton = document.getElementById('clear-mask-button');
    const maskIntervalSelect = document.getElementById('mask-interval-select');
    const maskOffsetSelect = document.getElementById('mask-offset-select');
    const maskInfo = document.getElementById('mask-info');
    let maskSelection = null; // {x, y, width, height} - 正規化された座標 (0-1)
    let maskSelectionBox = null; // DOM要素
    let currentMaskPageIndex = 0; // 現在選択中のページインデックス

    // --- 保存タブ要素 ---
    const gallerySave = document.getElementById('gallery-save');
    const savePdfButton = document.getElementById('save-pdf-button');
    const sizeSliderSave = document.getElementById('size-slider-save');

    // --- モーダル要素 ---
    const filenameModal = document.getElementById('filename-modal');
    const filenameInput = document.getElementById('filename-input');
    const modalDownloadButton = document.getElementById('modal-download-button');
    const modalCancelButton = document.getElementById('modal-cancel-button');

    // 初期状態設定
    setEditButtonsState(false);

    // ページ読み込み時にサーバー側のファイルをクリア
    (async () => {
        try {
            await fetch('/clear_all', { method: 'POST' });
        } catch (error) {
            console.error('初期化エラー:', error);
        }
    })();

    // ========================================
    // イベントリスナー
    // ========================================

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            loadDataToActiveTab();
        });
    });

    // ファイル選択時にファイル名を表示
    pdfFileInputs.forEach((input, index) => {
        input.addEventListener('change', () => {
            if (input.files[0]) {
                filenameDisplays[index].textContent = input.files[0].name;
                filenameDisplays[index].title = input.files[0].name; // ホバー時に全体を表示
            } else {
                filenameDisplays[index].textContent = '';
                filenameDisplays[index].title = '';
            }
        });
    });

    uploadButton.addEventListener('click', async () => {
        // 選択されているファイルを収集
        const selectedFiles = [];
        pdfFileInputs.forEach(input => {
            if (input.files[0]) {
                selectedFiles.push(input.files[0]);
            }
        });

        if (selectedFiles.length === 0) {
            status.textContent = 'ファイルが選択されていません。';
            return;
        }

        status.textContent = 'アップロード中... サムネイルを生成しています。';
        uploadButton.disabled = true;
        clearAllButton.disabled = true;

        try {
            // 選択された順にファイルをアップロード
            for (let i = 0; i < selectedFiles.length; i++) {
                const formData = new FormData();
                formData.append('pdfFile', selectedFiles[i]);

                status.textContent = `アップロード中 (${i + 1}/${selectedFiles.length})... サムネイルを生成しています。`;

                const response = await fetch('/upload', { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

                sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            }

            forceRepopulateAllGalleries(); // 全タブのギャラリーを再生成
            status.textContent = `${selectedFiles.length}個のファイルを追加しました。`;
            setEditButtonsState(true);
            await updateHistoryButtons(); // 履歴ボタンの状態を更新
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            uploadButton.disabled = false;
            clearAllButton.disabled = false;
            // すべてのファイル選択とファイル名表示をクリア
            pdfFileInputs.forEach((input, index) => {
                input.value = '';
                filenameDisplays[index].textContent = '';
                filenameDisplays[index].title = '';
            });
        }
    });

    clearAllButton.addEventListener('click', async () => {
        if (!confirm('本当にすべてのページをクリアしますか？')) return;
        
        status.textContent = 'クリア中...';
        try {
            const response = await fetch('/clear_all', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }
            resetAllStates();
            status.textContent = data.message;
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        }
    });

    [sizeSliderSplit, sizeSliderDelete, sizeSliderEdit, sizeSliderReorder, sizeSliderSave].forEach(slider => {
        slider.addEventListener('input', (e) => {
            document.documentElement.style.setProperty('--thumbnail-width', `${e.target.value}px`);
        });
    });

    // マスキング: 1つ目のプルダウン変更時に2つ目を更新
    maskIntervalSelect.addEventListener('change', () => {
        const interval = parseInt(maskIntervalSelect.value, 10);
        maskOffsetSelect.innerHTML = '';
        for (let i = 1; i <= interval; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i;
            maskOffsetSelect.appendChild(option);
        }
        // 最初のページ（1ページ目）にリセット
        currentMaskPageIndex = 0;
        loadMaskCanvas(0);
        clearMaskSelection();
        updateMaskGallerySelection();
    });

    // マスキング: 2つ目のプルダウン変更時にキャンバスを更新
    maskOffsetSelect.addEventListener('change', () => {
        const offset = parseInt(maskOffsetSelect.value, 10);
        // offset=1なら0番目、offset=2なら1番目...
        currentMaskPageIndex = offset - 1;
        loadMaskCanvas(offset - 1);
        clearMaskSelection();
        updateMaskGallerySelection();
    });

    // Undo/Redo機能
    undoButton.addEventListener('click', async () => {
        status.textContent = '元に戻しています...';
        undoButton.disabled = true;
        redoButton.disabled = true;
        try {
            const response = await fetch('/undo', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

            sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            resetAllSelections();
            forceRepopulateAllGalleries();
            status.textContent = data.message;
            await updateHistoryButtons();
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            await updateHistoryButtons();
        }
    });

    redoButton.addEventListener('click', async () => {
        status.textContent = 'やり直しています...';
        undoButton.disabled = true;
        redoButton.disabled = true;
        try {
            const response = await fetch('/redo', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

            sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            resetAllSelections();
            forceRepopulateAllGalleries();
            status.textContent = data.message;
            await updateHistoryButtons();
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            await updateHistoryButtons();
        }
    });

    // キーボードショートカット (Ctrl+Z, Ctrl+Y)
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'z' && !undoButton.disabled) {
            e.preventDefault();
            undoButton.click();
        } else if (e.ctrlKey && e.key === 'y' && !redoButton.disabled) {
            e.preventDefault();
            redoButton.click();
        }
    });

    // 履歴ボタンの状態を更新
    async function updateHistoryButtons() {
        try {
            const response = await fetch('/history_status');
            const data = await response.json();
            undoButton.disabled = !data.can_undo;
            redoButton.disabled = !data.can_redo;
        } catch (error) {
            console.error('履歴状態の更新エラー:', error);
        }
    }

    // マスキングギャラリーの選択状態を更新
    function updateMaskGallerySelection() {
        document.querySelectorAll('#gallery-mask .page-container').forEach(container => {
            const originalIndex = parseInt(container.dataset.originalIndex, 10);
            if (originalIndex === currentMaskPageIndex) {
                container.classList.add('selected-mask');
            } else {
                container.classList.remove('selected-mask');
            }
        });
    }

    // マスク選択をクリアする関数
    function clearMaskSelection() {
        maskSelection = null;
        if (maskSelectionBox) {
            maskSelectionBox.remove();
            maskSelectionBox = null;
        }
        maskInfo.textContent = '';
        applyMaskButton.disabled = true;
    }

    // ========================================
    // データロード & 状態リセット
    // ========================================

    function loadDataToActiveTab() {
        const activeTabContent = document.querySelector('.tab-content.active');
        if (!activeTabContent) return;
        const activeTabId = activeTabContent.id;

        placeholders.forEach(p => p.style.display = 'none');
        document.querySelectorAll('.gallery').forEach(g => g.style.display = 'none');

        if (activeTabId === 'upload-tab') {
            document.getElementById('gallery-upload').style.display = 'flex';
            if(sharedPdfData && !galleriesPopulated.upload) {
                populateGalleries(Array.from({ length: sharedPdfData.page_count }, (_, i) => i));
                galleriesPopulated.upload = true;
            }
            return;
        }

        if (activeTabId === 'mask-tab') {
            if (sharedPdfData) {
                activeTabContent.querySelector('.placeholder').style.display = 'none';
                maskCanvasContainer.style.display = 'inline-block';
                galleryMask.style.display = 'flex';
                if (!galleriesPopulated.mask) {
                    loadMaskCanvas(0);
                    currentMaskPageIndex = 0;
                    const orderToRender = Array.from({ length: sharedPdfData.page_count }, (_, i) => i);
                    populateGalleryMask(orderToRender);
                    galleriesPopulated.mask = true;
                }
            } else {
                activeTabContent.querySelector('.placeholder').style.display = 'block';
                maskCanvasContainer.style.display = 'none';
                galleryMask.style.display = 'none';
            }
            return;
        }

        if (sharedPdfData) {
            activeTabContent.querySelector('.placeholder').style.display = 'none';
            const gallery = activeTabContent.querySelector('.gallery');
            gallery.style.display = 'flex';

            // タブ名を取得（'split-tab' -> 'split'）
            const tabName = activeTabId.replace('-tab', '');

            // まだ生成されていない場合のみギャラリーを生成
            if (!galleriesPopulated[tabName]) {
                const orderToRender = Array.from({ length: sharedPdfData.page_count }, (_, i) => i);
                populateGalleries(orderToRender);
                galleriesPopulated[tabName] = true;
            }
        } else {
            activeTabContent.querySelector('.placeholder').style.display = 'block';
            activeTabContent.querySelector('.gallery').style.display = 'none';
        }
    }

    function populateGalleries(order) {
        const activeTabId = document.querySelector('.tab-content.active').id;
        switch (activeTabId) {
            case 'upload-tab': populateGalleryUpload(order); break;
            case 'split-tab': populateGallerySplit(order); break;
            case 'delete-tab': populateGalleryDelete(order); break;
            case 'edit-tab': populateGalleryEdit(order); break;
            case 'reorder-tab': populateGalleryReorder(order); break;
            case 'mask-tab': populateGalleryMask(order); break;
            case 'save-tab': populateGallerySave(order); break;
        }
    }

    function forceRepopulateAllGalleries() {
        // 全タブのギャラリーをクリアして再生成フラグをリセット
        [galleryUpload, gallerySplit, galleryDelete, galleryEdit, galleryReorder, galleryMask, gallerySave].forEach(g => { g.innerHTML = ''; });
        galleriesPopulated = {
            upload: false,
            split: false,
            delete: false,
            edit: false,
            reorder: false,
            mask: false,
            save: false
        };
        // アクティブタブを強制的に再生成
        if (sharedPdfData) {
            const orderToRender = Array.from({ length: sharedPdfData.page_count }, (_, i) => i);
            populateGalleries(orderToRender);
            const activeTabId = document.querySelector('.tab-content.active').id;
            const tabName = activeTabId.replace('-tab', '');
            galleriesPopulated[tabName] = true;
        }
    }

    function resetAllStates() {
        [galleryUpload, gallerySplit, galleryDelete, galleryEdit, galleryReorder, galleryMask, gallerySave].forEach(g => { g.innerHTML = ''; });
        galleriesPopulated = {
            upload: false,
            split: false,
            delete: false,
            edit: false,
            reorder: false,
            mask: false,
            save: false
        };
        status.textContent = '';
        sharedPdfData = null;
        resetAllSelections();
        setEditButtonsState(false);
    }
    
    function resetAllSelections() {
        selectedPagesToSplit = [];
        selectedPagesToDelete = [];
        selectedPagesToEdit = [];
        clickedOrder = [];
        selectedPagesToMove = [];
        document.querySelectorAll('.selected-split, .selected-delete, .selected-edit, .selected-reorder, .ordered').forEach(el => {
            el.classList.remove('selected-split', 'selected-delete', 'selected-edit', 'selected-reorder', 'ordered');
        });
        if (document.querySelector('#gallery-reorder')) updateGalleryOverlays();
    }

    function setEditButtonsState(enabled) {
        splitSelectedButton.disabled = !enabled;
        splitAllButton.disabled = !enabled;
        clearSelectionButtonSplit.disabled = !enabled;
        deleteButton.disabled = !enabled;
        clearSelectionButtonDelete.disabled = !enabled;
        rotateLeftButton.disabled = !enabled;
        rotateRightButton.disabled = !enabled;
        clearSelectionButtonEdit.disabled = !enabled;
        swapOddEvenButton.disabled = !enabled;
        reverseAllButton.disabled = !enabled;
        applyOrderButton.disabled = !enabled;
        clearSelectionButton.disabled = !enabled;
        movePrevButton.disabled = true;
        moveNextButton.disabled = true;
        savePdfButton.disabled = !enabled;
    }

    // ========================================
    // ギャラリー生成関数
    // ========================================

    function populateGalleryUpload(order) {
        galleryUpload.innerHTML = '';
        order.forEach((originalIndex) => {
            galleryUpload.appendChild(createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]));
        });
    }

    function populateGallerySplit(pageOrder) {
        gallerySplit.innerHTML = '';
        pageOrder.forEach((originalIndex) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);
            pageContainer.addEventListener('click', () => {
                const idx = parseInt(pageContainer.dataset.originalIndex, 10);
                const foundIndex = selectedPagesToSplit.indexOf(idx);
                if (foundIndex > -1) {
                    selectedPagesToSplit.splice(foundIndex, 1);
                    pageContainer.classList.remove('selected-split');
                } else {
                    selectedPagesToSplit.push(idx);
                    pageContainer.classList.add('selected-split');
                }
            });
            gallerySplit.appendChild(pageContainer);
        });
    }

    function populateGalleryDelete(pageOrder) {
        console.log('削除ギャラリー生成。ページ数:', sharedPdfData.page_count, 'ページ順序:', pageOrder);
        galleryDelete.innerHTML = '';
         pageOrder.forEach((originalIndex) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);
            const deleteOverlay = document.createElement('div');
            deleteOverlay.className = 'delete-overlay';
            deleteOverlay.textContent = '×';
            pageContainer.appendChild(deleteOverlay);
            pageContainer.addEventListener('click', () => {
                const idx = parseInt(pageContainer.dataset.originalIndex, 10);
                const foundIndex = selectedPagesToDelete.indexOf(idx);
                if (foundIndex > -1) {
                    selectedPagesToDelete.splice(foundIndex, 1);
                    pageContainer.classList.remove('selected-delete');
                } else {
                    selectedPagesToDelete.push(idx);
                    pageContainer.classList.add('selected-delete');
                }
                console.log('削除選択:', selectedPagesToDelete);
            });
            galleryDelete.appendChild(pageContainer);
        });
    }

    function populateGalleryEdit(pageOrder) {
        galleryEdit.innerHTML = '';
        pageOrder.forEach((originalIndex) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);
            pageContainer.addEventListener('click', () => {
                const idx = parseInt(pageContainer.dataset.originalIndex, 10);
                const foundIndex = selectedPagesToEdit.indexOf(idx);
                if (foundIndex > -1) {
                    selectedPagesToEdit.splice(foundIndex, 1);
                    pageContainer.classList.remove('selected-edit');
                } else {
                    selectedPagesToEdit.push(idx);
                    pageContainer.classList.add('selected-edit');
                }
            });
            galleryEdit.appendChild(pageContainer);
        });
    }

    function populateGalleryReorder(pageOrder) {
        galleryReorder.innerHTML = '';
        selectedPagesToMove = [];
        pageOrder.forEach((originalIndex) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);
            const orderOverlay = document.createElement('div');
            orderOverlay.className = 'order-overlay';
            pageContainer.appendChild(orderOverlay);
            pageContainer.addEventListener('click', () => {
                pageContainer.classList.toggle('selected-reorder');
                const indexInMoveSelection = selectedPagesToMove.indexOf(pageContainer);
                if (indexInMoveSelection > -1) selectedPagesToMove.splice(indexInMoveSelection, 1); else selectedPagesToMove.push(pageContainer);
                updateReorderButtonsState();
                const originalIdx = parseInt(pageContainer.dataset.originalIndex, 10);
                const indexInClickOrder = clickedOrder.indexOf(originalIdx);
                if (indexInClickOrder > -1) clickedOrder.splice(indexInClickOrder, 1); else clickedOrder.push(originalIdx);
                updateGalleryOverlays();
            });
            galleryReorder.appendChild(pageContainer);
        });
        updateGalleryOverlays();
        updateReorderButtonsState();
    }

    function populateGalleryMask(pageOrder) {
        galleryMask.innerHTML = '';
        pageOrder.forEach((originalIndex) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);

            // クリックでキャンバスを更新
            pageContainer.addEventListener('click', () => {
                // 全てのページから選択状態を削除
                document.querySelectorAll('#gallery-mask .page-container').forEach(c => c.classList.remove('selected-mask'));
                // クリックされたページを選択状態に
                pageContainer.classList.add('selected-mask');

                currentMaskPageIndex = originalIndex;
                loadMaskCanvas(originalIndex);
                clearMaskSelection();
            });

            // 初期表示時にプルダウンで選択されているページを選択状態に
            const currentOffset = parseInt(maskOffsetSelect.value, 10);
            if (originalIndex === currentOffset - 1) {
                pageContainer.classList.add('selected-mask');
            }

            galleryMask.appendChild(pageContainer);
        });
    }

    function populateGallerySave(pageOrder) {
        gallerySave.innerHTML = '';
        pageOrder.forEach((originalIndex) => {
            gallerySave.appendChild(createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]));
        });
    }

    // ========================================
    // 各タブの操作ロジック
    // ========================================

    async function performManipulation(url, statusMessage, options = { method: 'POST' }) {
        status.textContent = statusMessage;
        setEditButtonsState(false);
        try {
            const response = await fetch(url, options);
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }
            sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            resetAllSelections();
            forceRepopulateAllGalleries(); // 全タブのギャラリーを再生成
            status.textContent = data.message;
            await updateHistoryButtons(); // 履歴ボタンの状態を更新
            if (data.download_url) { // ダウンロードURLがあれば表示
                const downloadLink = document.getElementById(url.substring(1) + '-link'); // e.g. /split -> split-link
                if(downloadLink) {
                    downloadLink.href = data.download_url;
                    downloadLink.style.display = 'block';
                }
            }
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            setEditButtonsState(true);
        }
    }

    // --- ページ分割 ---
    splitSelectedButton.addEventListener('click', () => {
        if (selectedPagesToSplit.length === 0) { status.textContent = '分割するページを1つ以上選択してください。'; return; }
        performManipulation('/split', '選択したページを分割中...', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ pages_to_split: selectedPagesToSplit }) 
        });
    });
    splitAllButton.addEventListener('click', () => {
        performManipulation('/split', '全ページを分割中...', { method: 'POST' });
    });
    clearSelectionButtonSplit.addEventListener('click', () => {
        selectedPagesToSplit = [];
        document.querySelectorAll('#gallery-split .page-container.selected-split').forEach(c => c.classList.remove('selected-split'));
    });

    // --- ページ削除 ---
    deleteButton.addEventListener('click', () => {
        console.log('削除ボタンクリック。選択中のページ:', selectedPagesToDelete);
        if (selectedPagesToDelete.length === 0) {
            status.textContent = '削除するページを選択してください。';
            return;
        }
        performManipulation('/delete', `${selectedPagesToDelete.length}ページを削除中...`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pages_to_delete: selectedPagesToDelete })
        });
    });
    clearSelectionButtonDelete.addEventListener('click', () => {
        selectedPagesToDelete = [];
        document.querySelectorAll('#gallery-delete .page-container.selected-delete').forEach(c => c.classList.remove('selected-delete'));
    });

    // --- ページ編集 ---
    rotateLeftButton.addEventListener('click', () => rotatePages(-90));
    rotateRightButton.addEventListener('click', () => rotatePages(90));
    async function rotatePages(rotation) {
        if (selectedPagesToEdit.length === 0) { return; }
        await performManipulation('/rotate', `${selectedPagesToEdit.length}ページを回転中...`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ pages: selectedPagesToEdit, rotation: rotation }) 
        });
    }
    clearSelectionButtonEdit.addEventListener('click', () => {
        selectedPagesToEdit = [];
        document.querySelectorAll('#gallery-edit .page-container.selected-edit').forEach(c => c.classList.remove('selected-edit'));
    });
    swapOddEvenButton.addEventListener('click', () => performManipulation('/swap_odd_even', '偶数・奇数ページを入れ替え中...'));
    reverseAllButton.addEventListener('click', () => performManipulation('/reverse_all', '全ページを逆順にしています...'));

    // --- ページ並べ替え ---
    function getCircledNumber(num) {
        const circledNumbers = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩',
                                '⑪', '⑫', '⑬', '⑭', '⑮', '⑯', '⑰', '⑱', '⑲', '⑳',
                                '㉑', '㉒', '㉓', '㉔', '㉕', '㉖', '㉗', '㉘', '㉙', '㉚',
                                '㉛', '㉜', '㉝', '㉞', '㉟', '㊱', '㊲', '㊳', '㊴', '㊵',
                                '㊶', '㊷', '㊸', '㊹', '㊺', '㊻', '㊼', '㊽', '㊾', '㊿'];
        return num <= 50 ? circledNumbers[num - 1] : num.toString();
    }

    function updateGalleryOverlays() {
        document.querySelectorAll('#gallery-reorder .page-container').forEach(container => {
            const originalIndex = parseInt(container.dataset.originalIndex, 10);
            const orderIndex = clickedOrder.indexOf(originalIndex);
            const overlay = container.querySelector('.order-overlay');
            if (orderIndex > -1) {
                overlay.textContent = getCircledNumber(orderIndex + 1);
                container.classList.add('ordered');
            } else {
                overlay.textContent = '';
                container.classList.remove('ordered');
            }
        });
    }
    function updateReorderButtonsState() {
        const allPages = Array.from(galleryReorder.children);
        const hasSelection = selectedPagesToMove.length > 0;
        movePrevButton.disabled = !hasSelection || selectedPagesToMove.some(p => allPages.indexOf(p) === 0);
        moveNextButton.disabled = !hasSelection || selectedPagesToMove.some(p => allPages.indexOf(p) === allPages.length - 1);
    }
    clearSelectionButton.addEventListener('click', () => {
        selectedPagesToMove.forEach(page => page.classList.remove('selected-reorder'));
        selectedPagesToMove = [];
        clickedOrder = [];
        updateGalleryOverlays();
        updateReorderButtonsState();
    });
    applyOrderButton.addEventListener('click', () => {
        if (clickedOrder.length === 0) return;
        const currentOrder = Array.from(galleryReorder.children).map(c => parseInt(c.dataset.originalIndex, 10));
        const remainingPages = currentOrder.filter(index => !clickedOrder.includes(index));
        const newPageOrder = clickedOrder.concat(remainingPages);
        populateGalleryReorder(newPageOrder);
        clickedOrder = [];
        selectedPagesToMove = [];
    });
    movePrevButton.addEventListener('click', () => movePages('prev'));
    moveNextButton.addEventListener('click', () => movePages('next'));
    function movePages(direction) {
        if (selectedPagesToMove.length === 0) return;
        const pages = Array.from(galleryReorder.children);
        const selectedSorted = selectedPagesToMove.sort((a, b) => pages.indexOf(a) - pages.indexOf(b));
        if (direction === 'prev') {
            const firstSelected = selectedSorted[0];
            const targetNode = firstSelected.previousElementSibling;
            if (targetNode) {
                selectedSorted.forEach(page => galleryReorder.insertBefore(page, targetNode));
            }
        } else {
            const lastSelected = selectedSorted[selectedSorted.length - 1];
            const targetNode = lastSelected.nextElementSibling;
            if (targetNode) {
                selectedSorted.reverse().forEach(page => galleryReorder.insertBefore(page, targetNode.nextElementSibling));
            }
        }
        updateReorderButtonsState();
    }

    // --- PDF保存処理 ---
    savePdfButton.addEventListener('click', async () => {
        // 最初にアップロードしたファイル名を取得
        try {
            const response = await fetch('/get_original_filename');
            const data = await response.json();
            filenameInput.value = data.filename || 'edited';
            filenameModal.classList.add('show');
            filenameInput.focus();
            filenameInput.select();
        } catch (error) {
            console.error('ファイル名取得エラー:', error);
            filenameInput.value = 'edited';
            filenameModal.classList.add('show');
            filenameInput.focus();
            filenameInput.select();
        }
    });

    // モーダルのダウンロードボタン
    modalDownloadButton.addEventListener('click', async () => {
        const customFilename = filenameInput.value.trim() || 'edited';
        filenameModal.classList.remove('show');

        const pageContainers = Array.from(gallerySave.querySelectorAll('.page-container'));
        const finalOrder = pageContainers.map(c => parseInt(c.dataset.originalIndex, 10));
        if (finalOrder.length !== sharedPdfData.page_count) { return; }

        status.textContent = 'PDFを生成中...';
        setEditButtonsState(false);
        try {
            const response = await fetch('/reorder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order: finalOrder, filename: customFilename })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

            // PDFを自動ダウンロード
            const downloadUrl = data.download_url;
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = data.filename || 'edited.pdf';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            status.textContent = 'PDFのダウンロードを開始しました！';
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            setEditButtonsState(true);
        }
    });

    // モーダルのキャンセルボタン
    modalCancelButton.addEventListener('click', () => {
        filenameModal.classList.remove('show');
    });

    // モーダルの背景クリックで閉じる
    filenameModal.addEventListener('click', (e) => {
        if (e.target === filenameModal) {
            filenameModal.classList.remove('show');
        }
    });

    // Enterキーでダウンロード
    filenameInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            modalDownloadButton.click();
        }
    });

    // ========================================
    // ヘルパー関数
    // ========================================
    function createPageContainer(originalIndex, thumbUrl) {
        const pageContainer = document.createElement('div');
        pageContainer.className = 'page-container';
        pageContainer.dataset.originalIndex = originalIndex;
        const img = document.createElement('img');
        img.src = thumbUrl + '?t=' + new Date().getTime();
        const pageNum = document.createElement('div');
        pageNum.className = 'page-number';
        pageNum.textContent = `ページ ${originalIndex + 1}`;
        pageContainer.appendChild(img);
        pageContainer.appendChild(pageNum);
        return pageContainer;
    }

    // ========================================
    // マスキング機能
    // ========================================

    function loadMaskCanvas(pageIndex = 0) {
        if (!sharedPdfData || sharedPdfData.page_count === 0) return;

        // ページインデックスが範囲外の場合は最初のページを表示
        if (pageIndex < 0 || pageIndex >= sharedPdfData.page_count) {
            pageIndex = 0;
        }

        const pageThumb = sharedPdfData.thumbnails[pageIndex];
        const img = new Image();
        img.onload = function() {
            maskCanvas.width = img.width;
            maskCanvas.height = img.height;
            const ctx = maskCanvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
        };
        img.src = pageThumb;
    }

    let isDrawing = false;
    let startX, startY;

    maskCanvas.addEventListener('mousedown', (e) => {
        if (!sharedPdfData) return;
        isDrawing = true;
        const rect = maskCanvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;

        // 既存の選択ボックスを削除
        if (maskSelectionBox) {
            maskSelectionBox.remove();
            maskSelectionBox = null;
        }
    });

    maskCanvas.addEventListener('mousemove', (e) => {
        if (!isDrawing) return;

        const rect = maskCanvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;

        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);

        // 選択ボックスを更新
        if (!maskSelectionBox) {
            maskSelectionBox = document.createElement('div');
            maskSelectionBox.className = 'mask-selection-box';
            maskCanvasContainer.appendChild(maskSelectionBox);
        }

        maskSelectionBox.style.left = x + 'px';
        maskSelectionBox.style.top = y + 'px';
        maskSelectionBox.style.width = width + 'px';
        maskSelectionBox.style.height = height + 'px';
    });

    maskCanvas.addEventListener('mouseup', (e) => {
        if (!isDrawing) return;
        isDrawing = false;

        const rect = maskCanvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;

        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);

        // 正規化された座標を保存 (0-1の範囲)
        maskSelection = {
            x: x / maskCanvas.width,
            y: y / maskCanvas.height,
            width: width / maskCanvas.width,
            height: height / maskCanvas.height
        };

        maskInfo.textContent = `選択領域: (${Math.round(x)}, ${Math.round(y)}) - ${Math.round(width)} × ${Math.round(height)}px`;
        applyMaskButton.disabled = false;
        clearMaskButton.disabled = false;
    });

    clearMaskButton.addEventListener('click', () => {
        clearMaskSelection();
        clearMaskButton.disabled = true;
    });

    // マスキング適用処理
    applyMaskButton.addEventListener('click', async () => {
        if (!maskSelection) return;

        const interval = parseInt(maskIntervalSelect.value, 10);
        const offset = parseInt(maskOffsetSelect.value, 10);

        status.textContent = `${interval}ページ毎に${offset}ページ目にマスキングを適用中...`;
        applyMaskButton.disabled = true;
        clearMaskButton.disabled = true;

        try {
            const response = await fetch('/apply_mask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mask: maskSelection, interval: interval, offset: offset })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

            sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            forceRepopulateAllGalleries();

            // マスク選択をクリア
            maskSelection = null;
            if (maskSelectionBox) {
                maskSelectionBox.remove();
                maskSelectionBox = null;
            }
            maskInfo.textContent = '';

            // キャンバスを再読み込み（現在選択されているページで）
            galleriesPopulated.mask = false;
            const currentOffset = parseInt(maskOffsetSelect.value, 10);
            loadMaskCanvas(currentOffset - 1);

            status.textContent = data.message;
            await updateHistoryButtons(); // 履歴ボタンの状態を更新
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            applyMaskButton.disabled = false;
            clearMaskButton.disabled = false;
        }
    });
});