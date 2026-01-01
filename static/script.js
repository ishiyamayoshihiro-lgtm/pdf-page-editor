/*
 * PDF編集Webアプリケーション - メインスクリプト
 * (c) 2025 IshiyamaYoshihiro
 * License: MIT License
 */

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
        'file-split': false,
        mask: false,
        'split-files': false,
        save: false
    };
    let fileSplitPositions = []; // 選択された分割位置の配列

    // --- 共通要素 ---
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const placeholders = document.querySelectorAll('.placeholder');
    const status = document.getElementById('status');
    const undoButton = document.getElementById('undo-button');
    const redoButton = document.getElementById('redo-button');

    // --- アップロードタブ要素 ---
    const dropZone = document.getElementById('drop-zone');
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

    // --- ファイル分割タブ要素 ---
    const galleryFileSplit = document.getElementById('gallery-file-split');
    const executeFileSplitButton = document.getElementById('execute-file-split-button');
    const clearSplitLinesButton = document.getElementById('clear-split-lines-button');
    const sizeSliderFileSplit = document.getElementById('size-slider-file-split');

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

    // --- ページ分割保存タブ要素 ---
    const gallerySplitFiles = document.getElementById('gallery-split-files');
    const splitToFilesButton = document.getElementById('split-to-files-button');
    const splitFilesAsImageCheckbox = document.getElementById('split-files-as-image-checkbox');
    const splitFilesDpiContainer = document.getElementById('split-files-dpi-container');
    const splitFilesDpiSelect = document.getElementById('split-files-dpi-select');
    const sizeSliderSplitFiles = document.getElementById('size-slider-split-files');

    // --- 保存タブ要素 ---
    const gallerySave = document.getElementById('gallery-save');
    const savePdfButton = document.getElementById('save-pdf-button');
    const saveImagePdfButton = document.getElementById('save-image-pdf-button');
    const imagePdfDpiSelect = document.getElementById('image-pdf-dpi-select');
    const sizeSliderSave = document.getElementById('size-slider-save');

    // --- モーダル要素 ---
    const filenameModal = document.getElementById('filename-modal');
    const filenameInput = document.getElementById('filename-input');
    const modalDownloadButton = document.getElementById('modal-download-button');
    const modalCancelButton = document.getElementById('modal-cancel-button');

    // --- ファイル分割モーダル要素 ---
    const fileSplitModal = document.getElementById('file-split-modal');
    const splitPartsContainer = document.getElementById('split-parts-container');
    const modalSplitSaveButton = document.getElementById('modal-split-save-button');
    const modalSplitCancelButton = document.getElementById('modal-split-cancel-button');

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
    // ファイル処理関数
    // ========================================
    async function handleFiles(files) {
        if (files.length === 0) {
            status.textContent = 'ファイルが選択されていません。';
            return;
        }

        const pdfFiles = Array.from(files).filter(file => file.name.toLowerCase().endsWith('.pdf'));
        if (pdfFiles.length === 0) {
            status.textContent = 'PDFファイルを選択またはドラッグ＆ドロップしてください。';
            return;
        }
        
        if (pdfFiles.length > 5) {
            status.textContent = '一度にアップロードできるファイルは5つまでです。';
            return;
        }

        status.textContent = 'アップロード中... サムネイルを生成しています。';
        uploadButton.disabled = true;
        clearAllButton.disabled = true;

        try {
            for (let i = 0; i < pdfFiles.length; i++) {
                const formData = new FormData();
                formData.append('pdfFile', pdfFiles[i]);

                status.textContent = `アップロード中 (${i + 1}/${pdfFiles.length})... サムネイルを生成しています。`;

                const response = await fetch('/upload', { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

                sharedPdfData = { page_count: data.page_count, thumbnails: data.thumbnails };
            }

            forceRepopulateAllGalleries();
            status.textContent = `${pdfFiles.length}個のPDFファイルを追加しました。`;
            setEditButtonsState(true);
            await updateHistoryButtons();
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            uploadButton.disabled = false;
            clearAllButton.disabled = false;
            pdfFileInputs.forEach((input, index) => {
                input.value = '';
                filenameDisplays[index].textContent = '';
                filenameDisplays[index].title = '';
            });
        }
    }

    // ========================================
    // イベントリスナー
    // ========================================

    // グループタブの切り替え
    const groupTabButtons = document.querySelectorAll('.group-tab-button');
    const subTabGroups = document.querySelectorAll('.sub-tab-group');

    groupTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetGroup = button.dataset.group;
            groupTabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            subTabGroups.forEach(group => {
                if (group.dataset.group === targetGroup) {
                    group.classList.add('active');
                    const firstTab = group.querySelector('.tab-button');
                    if (firstTab) {
                        firstTab.click();
                    }
                } else {
                    group.classList.remove('active');
                }
            });
        });
    });

    // サブタブの切り替え
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            const parentGroup = button.closest('.sub-tab-group');
            if (parentGroup) {
                parentGroup.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            }
            tabContents.forEach(content => content.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            loadDataToActiveTab();
        });
    });

    // --- ドラッグ＆ドロップイベントリスナー ---
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });

    // ファイル選択時にファイル名を表示
    pdfFileInputs.forEach((input, index) => {
        input.addEventListener('change', () => {
            if (input.files[0]) {
                filenameDisplays[index].textContent = input.files[0].name;
                filenameDisplays[index].title = input.files[0].name;
            } else {
                filenameDisplays[index].textContent = '';
                filenameDisplays[index].title = '';
            }
        });
    });

    // アップロードボタンのクリック
    uploadButton.addEventListener('click', () => {
        const selectedFiles = [];
        pdfFileInputs.forEach(input => {
            if (input.files[0]) {
                selectedFiles.push(input.files[0]);
            }
        });
        handleFiles(selectedFiles);
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

    [sizeSliderSplit, sizeSliderDelete, sizeSliderEdit, sizeSliderReorder, sizeSliderFileSplit, sizeSliderSplitFiles, sizeSliderSave].forEach(slider => {
        slider.addEventListener('input', (e) => {
            document.documentElement.style.setProperty('--thumbnail-width', `${e.target.value}px`);
        });
    });

    splitFilesAsImageCheckbox.addEventListener('change', () => {
        splitFilesDpiContainer.style.display = splitFilesAsImageCheckbox.checked ? 'block' : 'none';
    });

    maskIntervalSelect.addEventListener('change', () => {
        const interval = parseInt(maskIntervalSelect.value, 10);
        maskOffsetSelect.innerHTML = '';
        for (let i = 1; i <= interval; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i;
            maskOffsetSelect.appendChild(option);
        }
        currentMaskPageIndex = 0;
        loadMaskCanvas(0);
        clearMaskSelection();
        updateMaskGallerySelection();
    });

    maskOffsetSelect.addEventListener('change', () => {
        const offset = parseInt(maskOffsetSelect.value, 10);
        currentMaskPageIndex = offset - 1;
        loadMaskCanvas(offset - 1);
        clearMaskSelection();
        updateMaskGallerySelection();
    });

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

    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'z' && !undoButton.disabled) {
            e.preventDefault();
            undoButton.click();
        } else if (e.ctrlKey && e.key === 'y' && !redoButton.disabled) {
            e.preventDefault();
            redoButton.click();
        }
    });

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

    function updateMaskGallerySelection() {
        document.querySelectorAll('#gallery-mask .page-container').forEach(container => {
            const originalIndex = parseInt(container.dataset.originalIndex, 10);
            container.classList.toggle('selected-mask', originalIndex === currentMaskPageIndex);
        });
    }

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

            const tabName = activeTabId.replace('-tab', '');
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
            case 'file-split-tab': populateGalleryFileSplit(order); break;
            case 'mask-tab': populateGalleryMask(order); break;
            case 'split-files-tab': populateGallerySplitFiles(order); break;
            case 'save-tab': populateGallerySave(order); break;
        }
    }

    function forceRepopulateAllGalleries() {
        Object.keys(galleriesPopulated).forEach(key => galleriesPopulated[key] = false);
        [galleryUpload, gallerySplit, galleryDelete, galleryEdit, galleryReorder, galleryFileSplit, galleryMask, gallerySplitFiles, gallerySave].forEach(g => { g.innerHTML = ''; });
        if (sharedPdfData) {
            const orderToRender = Array.from({ length: sharedPdfData.page_count }, (_, i) => i);
            populateGalleries(orderToRender);
            const activeTabId = document.querySelector('.tab-content.active').id;
            const tabName = activeTabId.replace('-tab', '');
            galleriesPopulated[tabName] = true;
        }
    }

    function resetAllStates() {
        forceRepopulateAllGalleries();
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
        fileSplitPositions = [];
        document.querySelectorAll('.selected-split, .selected-delete, .selected-edit, .selected-reorder, .ordered').forEach(el => {
            el.classList.remove('selected-split', 'selected-delete', 'selected-edit', 'selected-reorder', 'ordered');
        });
        document.querySelectorAll('.split-line.active').forEach(el => el.classList.remove('active'));
        if (document.querySelector('#gallery-reorder')) updateGalleryOverlays();
    }

    function setEditButtonsState(enabled) {
        const buttons = [
            splitSelectedButton, splitAllButton, clearSelectionButtonSplit,
            deleteButton, clearSelectionButtonDelete, rotateLeftButton,
            rotateRightButton, clearSelectionButtonEdit, swapOddEvenButton,
            reverseAllButton, applyOrderButton, clearSelectionButton,
            splitToFilesButton, savePdfButton, saveImagePdfButton
        ];
        buttons.forEach(btn => btn.disabled = !enabled);
        movePrevButton.disabled = true;
        moveNextButton.disabled = true;
        executeFileSplitButton.disabled = true;
        clearSplitLinesButton.disabled = true;
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
            pageContainer.addEventListener('click', () => {
                document.querySelectorAll('#gallery-mask .page-container').forEach(c => c.classList.remove('selected-mask'));
                pageContainer.classList.add('selected-mask');
                currentMaskPageIndex = originalIndex;
                loadMaskCanvas(originalIndex);
                clearMaskSelection();
            });
            if (originalIndex === (parseInt(maskOffsetSelect.value, 10) - 1)) {
                pageContainer.classList.add('selected-mask');
            }
            galleryMask.appendChild(pageContainer);
        });
    }

    function populateGalleryFileSplit(pageOrder) {
        galleryFileSplit.innerHTML = '';
        pageOrder.forEach((originalIndex, index) => {
            const pageContainer = createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]);
            galleryFileSplit.appendChild(pageContainer);

            if (index < pageOrder.length - 1) {
                const splitLine = document.createElement('div');
                splitLine.className = 'split-line';
                splitLine.dataset.position = originalIndex + 1;
                splitLine.title = `${originalIndex + 1}ページと${originalIndex + 2}ページの間で分割`;
                splitLine.addEventListener('click', () => {
                    const position = parseInt(splitLine.dataset.position, 10);
                    const posIndex = fileSplitPositions.indexOf(position);
                    if (posIndex > -1) {
                        fileSplitPositions.splice(posIndex, 1);
                        splitLine.classList.remove('active');
                    } else {
                        fileSplitPositions.push(position);
                        splitLine.classList.add('active');
                    }
                    executeFileSplitButton.disabled = fileSplitPositions.length === 0;
                    clearSplitLinesButton.disabled = fileSplitPositions.length === 0;
                });
                galleryFileSplit.appendChild(splitLine);
            }
        });
    }

    function populateGallerySplitFiles(pageOrder) {
        gallerySplitFiles.innerHTML = '';
        pageOrder.forEach((originalIndex) => {
            gallerySplitFiles.appendChild(createPageContainer(originalIndex, sharedPdfData.thumbnails[originalIndex]));
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
            forceRepopulateAllGalleries();
            status.textContent = data.message;
            await updateHistoryButtons();
            if (data.download_url) {
                const downloadLink = document.getElementById(url.substring(1) + '-link');
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

    deleteButton.addEventListener('click', () => {
        if (selectedPagesToDelete.length === 0) { status.textContent = '削除するページを選択してください。'; return; }
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

    executeFileSplitButton.addEventListener('click', () => {
        if (fileSplitPositions.length === 0) { status.textContent = '分割位置を選択してください。'; return; }
        const sortedPositions = [...fileSplitPositions].sort((a, b) => a - b);
        const parts = [];
        let start = 0;
        sortedPositions.forEach(pos => {
            parts.push({ start: start, end: pos });
            start = pos;
        });
        parts.push({ start: start, end: sharedPdfData.page_count });
        splitPartsContainer.innerHTML = '';
        parts.forEach((part, index) => {
            const partRow = document.createElement('div');
            partRow.className = 'split-part-row';
            partRow.innerHTML = `
                <label class="split-part-label">
                    <input type="checkbox" class="split-part-skip" data-index="${index}">
                    <span>保存不要</span>
                </label>
                <span class="split-part-range">${part.start + 1}～${part.end}ページ</span>
                <input type="text" class="split-part-filename" data-index="${index}" placeholder="ファイル名を入力" value="part${index + 1}">
            `;
            splitPartsContainer.appendChild(partRow);
        });
        fileSplitModal.dataset.parts = JSON.stringify(parts);
        fileSplitModal.classList.add('show');
    });

    clearSplitLinesButton.addEventListener('click', () => {
        fileSplitPositions = [];
        document.querySelectorAll('#gallery-file-split .split-line.active').forEach(line => line.classList.remove('active'));
        executeFileSplitButton.disabled = true;
        clearSplitLinesButton.disabled = true;
    });

    modalSplitSaveButton.addEventListener('click', async () => {
        const parts = JSON.parse(fileSplitModal.dataset.parts || '[]');
        const partsData = parts.map((part, index) => ({
            start: part.start,
            end: part.end,
            filename: document.querySelector(`.split-part-filename[data-index="${index}"]`).value.trim(),
            save: !document.querySelector(`.split-part-skip[data-index="${index}"]`).checked
        }));

        if (partsData.filter(p => p.save && p.filename).length === 0) {
            alert('保存するファイル名を少なくとも1つ入力してください。');
            return;
        }

        fileSplitModal.classList.remove('show');
        status.textContent = '分割ファイルを生成中...';
        executeFileSplitButton.disabled = true;
        clearSplitLinesButton.disabled = true;

        try {
            const response = await fetch('/split_and_save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parts: partsData })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }

            for (let i = 0; i < data.files.length; i++) {
                const file = data.files[i];
                const link = document.createElement('a');
                link.href = file.url;
                link.download = file.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                if (i < data.files.length - 1) await new Promise(resolve => setTimeout(resolve, 500));
            }
            status.textContent = `${data.message}（${data.files.length}個のファイルをダウンロード開始）`;
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            executeFileSplitButton.disabled = fileSplitPositions.length === 0;
            clearSplitLinesButton.disabled = fileSplitPositions.length === 0;
        }
    });

    modalSplitCancelButton.addEventListener('click', () => fileSplitModal.classList.remove('show'));
    fileSplitModal.addEventListener('click', (e) => { if (e.target === fileSplitModal) fileSplitModal.classList.remove('show'); });

    function getCircledNumber(num) {
        const circledNumbers = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩', '⑪', '⑫', '⑬', '⑭', '⑮', '⑯', '⑰', '⑱', '⑲', '⑳', '㉑', '㉒', '㉓', '㉔', '㉕', '㉖', '㉗', '㉘', '㉙', '㉚', '㉛', '㉜', '㉝', '㉞', '㉟', '㊱', '㊲', '㊳', '㊴', '㊵', '㊶', '㊷', '㊸', '㊹', '㊺', '㊻', '㊼', '㊽', '㊾', '㊿'];
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
            if (targetNode) selectedSorted.forEach(page => galleryReorder.insertBefore(page, targetNode));
        } else {
            const lastSelected = selectedSorted[selectedSorted.length - 1];
            const targetNode = lastSelected.nextElementSibling;
            if (targetNode) selectedSorted.reverse().forEach(page => galleryReorder.insertBefore(page, targetNode.nextElementSibling));
        }
        updateReorderButtonsState();
    }

    splitToFilesButton.addEventListener('click', async () => {
        if (!sharedPdfData || sharedPdfData.page_count === 0) { status.textContent = 'PDFがアップロードされていません。'; return; }
        const convertToImage = splitFilesAsImageCheckbox.checked;
        const dpi = convertToImage ? parseInt(splitFilesDpiSelect.value, 10) : 150;
        status.textContent = convertToImage ? `PDFを画像PDFとして個別ファイルに分割中（${dpi} DPI）...` : 'PDFを個別ファイルに分割中...';
        splitToFilesButton.disabled = true;
        try {
            const response = await fetch('/split_to_files', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ convert_to_image: convertToImage, dpi: dpi })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            status.textContent = `${data.message}（ZIPファイルとしてダウンロード開始）`;
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            splitToFilesButton.disabled = false;
        }
    });

    savePdfButton.addEventListener('click', async () => {
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
            const link = document.createElement('a');
            link.href = data.download_url;
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

    modalCancelButton.addEventListener('click', () => filenameModal.classList.remove('show'));
    filenameModal.addEventListener('click', (e) => { if (e.target === filenameModal) filenameModal.classList.remove('show'); });
    filenameInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') modalDownloadButton.click(); });

    saveImagePdfButton.addEventListener('click', async () => {
        if (!sharedPdfData || sharedPdfData.page_count === 0) { status.textContent = 'PDFがアップロードされていません。'; return; }
        try {
            const filenameResponse = await fetch('/get_original_filename');
            const filenameData = await filenameResponse.json();
            const baseFilename = filenameData.filename || 'image_pdf';
            const dpi = parseInt(imagePdfDpiSelect.value, 10);
            status.textContent = `PDFを画像PDFに変換中（${dpi} DPI）...`;
            saveImagePdfButton.disabled = true;
            const response = await fetch('/convert_to_image_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: baseFilename, dpi: dpi })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || 'サーバーエラー'); }
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            status.textContent = data.message;
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
        } finally {
            saveImagePdfButton.disabled = false;
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
        if (pageIndex < 0 || pageIndex >= sharedPdfData.page_count) pageIndex = 0;
        const pageThumb = sharedPdfData.thumbnails[pageIndex];
        const img = new Image();
        img.onload = function() {
            maskCanvas.width = img.width;
            maskCanvas.height = img.height;
            maskCanvas.getContext('2d').drawImage(img, 0, 0);
        };
        img.src = pageThumb;
    }

    let isDrawing = false;
    let startX, startY;

    maskCanvas.addEventListener('mousedown', (e) => {
        if (!sharedPdfData) return;
        isDrawing = true;
        const rect = maskCanvas.getBoundingClientRect();
        // キャンバスのスケール比を考慮して座標を計算
        const scaleX = maskCanvas.width / rect.width;
        const scaleY = maskCanvas.height / rect.height;
        startX = (e.clientX - rect.left) * scaleX;
        startY = (e.clientY - rect.top) * scaleY;
        if (maskSelectionBox) maskSelectionBox.remove();
    });

    maskCanvas.addEventListener('mousemove', (e) => {
        if (!isDrawing) return;
        const rect = maskCanvas.getBoundingClientRect();
        const scaleX = maskCanvas.width / rect.width;
        const scaleY = maskCanvas.height / rect.height;
        const currentX = (e.clientX - rect.left) * scaleX;
        const currentY = (e.clientY - rect.top) * scaleY;
        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);
        if (!maskSelectionBox) {
            maskSelectionBox = document.createElement('div');
            maskSelectionBox.className = 'mask-selection-box';
            maskCanvasContainer.appendChild(maskSelectionBox);
        }
        // 表示用の座標はスケールを逆変換
        maskSelectionBox.style.left = (x / scaleX) + 'px';
        maskSelectionBox.style.top = (y / scaleY) + 'px';
        maskSelectionBox.style.width = (width / scaleX) + 'px';
        maskSelectionBox.style.height = (height / scaleY) + 'px';
    });

    maskCanvas.addEventListener('mouseup', (e) => {
        if (!isDrawing) return;
        isDrawing = false;
        const rect = maskCanvas.getBoundingClientRect();
        const scaleX = maskCanvas.width / rect.width;
        const scaleY = maskCanvas.height / rect.height;
        const endX = (e.clientX - rect.left) * scaleX;
        const endY = (e.clientY - rect.top) * scaleY;
        const x = Math.min(startX, endX);
        const y = Math.min(startY, endY);
        const width = Math.abs(endX - startX);
        const height = Math.abs(endY - startY);
        // 正規化された座標(0-1)に変換
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
            clearMaskSelection();
            galleriesPopulated.mask = false;
            loadMaskCanvas(parseInt(maskOffsetSelect.value, 10) - 1);
            status.textContent = data.message;
            await updateHistoryButtons();
        } catch (error) {
            status.textContent = `エラー: ${error.message}`;
            applyMaskButton.disabled = false;
            clearMaskButton.disabled = false;
        }
    });
});