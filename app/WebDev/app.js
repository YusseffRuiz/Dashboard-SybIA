document.addEventListener('DOMContentLoaded', () => {

    // --- Referencias al DOM ---
    const recordBtn = document.getElementById('record-btn');
    const recordingStatus = document.getElementById('recording-status');
    const branchSelect = document.getElementById('branch-select');
    const recognizedText = document.getElementById('recognized-text');

    // Registrar el Plugin de Datalabels globalmente
    if (typeof ChartDataLabels !== 'undefined') {
        Chart.register(ChartDataLabels);
    }

    // Configuración de Audio y Gráficas
    let isRecording = false;
    let mediaRecorder = null;
    let audioChunks = [];

    let chartInstances = {}; // Almacena mapeo id_canvas -> nueva Chart()
    let currentDataSets = []; // Estado actual de la lista de datasets a graficar

    // Estados para Gestión de Vistas Avanzadas
    let allChartDatasets = [];
    let hiddenChartIds = new Set(); // Ids de graficas que el usuario ocultó
    let maximizedChartIds = new Set(); // Ids de graficas expandidas a full width manualmente

    // --- 1. Obtener Sucursales (Desde la API SQL en Python) ---
    async function loadBranches() {
        try {
            const res = await fetch('https://nonspontaneous-befuddledly-patrina.ngrok-free.dev/get-sucursales', {
                method: 'GET',
                headers: {
                    'ngrok-skip-browser-warning': '69420' // Header para pasar por ngrok
                }
            });
            const branches = await res.json();

            branchSelect.innerHTML = '<option value="" disabled selected>Selecciona una sucursal</option>';
            branches.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.id_Cliente;
                opt.textContent = b.Cliente;
                branchSelect.appendChild(opt);
            });
        } catch (err) {
            console.error('No se pudo conectar a la API que sirve SQL:', err);
            const fallbackData = [{ id_Cliente: 1, Cliente: "API Inactiva - Conecta Python 8085" }];
            branchSelect.innerHTML = '<option value="" disabled selected>API de Sucursales no conectada</option>';
            fallbackData.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id_Cliente; opt.textContent = f.Cliente;
                branchSelect.appendChild(opt);
            });
        }
    }

    // --- 2. Lógica de Control por Voz y Audio ---
    recordBtn.addEventListener('click', async () => {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                sendAudioToApi(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            isRecording = true;
            recordBtn.classList.add('recording');
            recordingStatus.textContent = "Grabando... (Click en el icono para detener)";
            recordingStatus.classList.add('active');
            recognizedText.textContent = "";
        } catch (err) {
            console.error("Error accediendo al micrófono:", err);
            alert("No se pudo iniciar el grabador. Comprueba tú configuración de permisos de micrófono.");
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordingStatus.classList.remove('active');
    }

    // --- 3. Envío al Backend API Python ---
    async function sendAudioToApi(blob) {

        const idCliente = branchSelect.value;
        if (!idCliente || idCliente === "") {
            alert("⚠️ Selecciona un Cliente/Sucursal en la esquina superior primero.");
            return;
        }

        recordBtn.disabled = true;
        recordingStatus.innerHTML = '<span class="spinner"></span> Recuperando información...';
        recognizedText.textContent = "";

        try {
            const formData = new FormData();
            formData.append('file', blob, 'prueba.wav');

            const response = await fetch(`https://nonspontaneous-befuddledly-patrina.ngrok-free.dev/analyze-voice?id_cliente=${idCliente}`, {
                method: 'POST',
                headers: { 'accept': 'application/json' },
                body: formData
            });

            if (response.ok) {
                const apiData = await response.json();
                recordingStatus.textContent = "Consulta exitosa.";
                recognizedText.textContent = `"${apiData.transcript || 'Procesada'}"`;

                setTimeout(() => {
                    recordingStatus.textContent = "Presiona para grabar tu consulta";
                }, 8000);

                const datasets = processChartData(apiData);
                if (datasets.length === 0) {
                    alert("La consulta se procesó pero no hay datos estructurados para graficar.");
                    return;
                }

                // Reinicia layout state al inyectar nueva consulta SQL
                allChartDatasets = datasets;
                hiddenChartIds = new Set();
                maximizedChartIds = new Set();
                updateUI();

            } else {
                throw new Error("Respuesta no OK, status: " + response.status);
            }
        } catch (error) {
            console.error("Error transmitiendo audio a la API:", error);
            recordingStatus.textContent = "⛔ Error de conexión con tu API local 127.0.0.1:8085. Revisa la consola.";
        } finally {
            recordBtn.disabled = false;
        }
    }

    // --- 4. Parseador Multi-Dimensional de Datos ---
    function processChartData(response) {
        let datasets = [];

        // A) Caso Dashboard General
        if (response.intent === 'dashboard_general' && response.data) {

            // 1. Resumen General
            if (response.data.resumen && response.data.resumen.length > 0) {
                const res = response.data.resumen[0];
                let labels = ['Titulares', 'Beneficiarios'];
                let values = [res.titulares || 0, res.beneficiarios || 0];
                datasets.push({
                    id: 'chart_resumen_afiliacion',
                    title: 'Distribución por Afiliación',
                    labels: labels,
                    values: values,
                    recommendedType: 'pie'
                });

                let labelsEdades = ['Menores', 'Mayores', 'Sin Registro'];
                let valuesEdades = [res.menores || 0, res.mayores || 0, res.sin_fecha_nacimiento || 0];
                datasets.push({
                    id: 'chart_resumen_edad',
                    title: 'Distribución de Edades',
                    labels: labelsEdades,
                    values: valuesEdades,
                    recommendedType: 'doughnut'
                });

                let labelsGenero = ['Masculino', 'Femenino'];
                let valuesGenero = [res.masculino || 0, res.femenino || 0];
                datasets.push({
                    id: 'chart_resumen_genero',
                    title: 'Distribución por Género',
                    labels: labelsGenero,
                    values: valuesGenero,
                    recommendedType: 'pie'
                });
            }
            // 2. Historico (Timeline)
            if (response.data.timeline && response.data.timeline.length > 0) {
                let labels = [];
                let values = [];
                response.data.timeline.forEach(r => {
                    labels.push(`${r.Mes} ${r.Anio || ''}`.trim());
                    values.push(r.Total);
                });
                datasets.push({
                    id: 'chart_timeline',
                    title: 'Histórico de Asistencia Mensual',
                    labels: labels,
                    values: values,
                    recommendedType: 'line'
                });
            }
        }
        // B) Caso Específico Dinámico
        else if (response.data && Array.isArray(response.data) && response.data.length > 0) {
            const rows = response.data;
            let labels = [];
            let values = [];
            let recommendedType = response.chart_type || 'bar';
            let title = "Resultados Analíticos";

            if (rows[0].hasOwnProperty('Mes') && rows[0].hasOwnProperty('Total')) {
                rows.forEach(r => {
                    labels.push(`${r.Mes} ${r.Anio || ''}`.trim());
                    values.push(r.Total);
                });
                title = "Tendencia de Volumen Mensual";
            }
            else if (rows.length === 1) {
                const row = rows[0];
                for (let key in row) {
                    if (typeof row[key] === 'number' && key !== 'total' && key !== 'id_Cliente' && key !== 'Anio' && key !== 'MesNum') {
                        const cleanKey = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
                        labels.push(cleanKey);
                        values.push(row[key]);
                    }
                }
                recommendedType = 'doughnut';
                title = "Comparativa Detallada";
            }
            else {
                const keys = Object.keys(rows[0]);
                const dimKey = keys[0];
                const valKey = keys.length > 1 ? keys[1] : keys[0];
                rows.forEach(r => {
                    labels.push(r[dimKey]);
                    values.push(r[valKey]);
                });
                title = "Agrupación de Datos";
            }

            datasets.push({
                id: 'chart_single',
                title: title,
                labels: labels,
                values: values,
                recommendedType: recommendedType
            });
        }
        return datasets;
    }

    // --- 5. Renderizado y Gestión de Layouts UI Dinámicos ---
    function updateUI() {
        const visibleDatasets = allChartDatasets.filter(ds => !hiddenChartIds.has(ds.id));
        const hiddenDatasets = allChartDatasets.filter(ds => hiddenChartIds.has(ds.id));

        renderSidebar(hiddenDatasets);
        renderVisibleCharts(visibleDatasets);
    }

    function renderSidebar(hiddenDatasets) {
        const list = document.getElementById('hidden-charts-list');
        list.innerHTML = '';

        if (hiddenDatasets.length === 0) {
            list.innerHTML = '<div class="empty-hidden-state">No hay gráficas ocultas</div>';
            return;
        }

        hiddenDatasets.forEach(ds => {
            const item = document.createElement('div');
            item.className = 'hidden-chart-item';
            item.draggable = true;
            item.setAttribute('data-restore-id', ds.id);
            item.title = "Doble Click para restaurar, o arrastra hacia la derecha";

            item.innerHTML = `
                <span>${ds.title}</span>
                <svg class="chart-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
            `;

            item.addEventListener('dragstart', (e) => {
                item.classList.add('dragging');
                item.setAttribute('data-dragging-hidden', 'true');
            });

            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                item.removeAttribute('data-dragging-hidden');
            });

            item.addEventListener('dblclick', () => {
                hiddenChartIds.delete(ds.id);
                updateUI();
            });

            list.appendChild(item);
        });
    }

    function renderVisibleCharts(visibleDatasets) {
        const grid = document.getElementById('charts-grid');
        const emptyState = document.getElementById('global-empty-state');

        if (emptyState) emptyState.style.display = 'none';

        // Limpiamos para reconstruir tarjetas dinámicamente
        grid.innerHTML = '';

        for (let key in chartInstances) {
            if (chartInstances[key]) chartInstances[key].destroy();
        }
        chartInstances = {};
        currentDataSets = visibleDatasets;

        if (visibleDatasets.length === 0 && allChartDatasets.length === 0) {
            if (emptyState) {
                emptyState.style.display = 'block';
                grid.appendChild(emptyState);
            }
            return;
        } else if (visibleDatasets.length === 0) {
            grid.innerHTML = '<div class="empty-state" style="margin-top: 2rem;"><p>Has ocultado todas las gráficas. Arrástralas desde el panel izquierdo.</p></div>';
            attachGridRestoreDropEvent(grid);
            return;
        }

        visibleDatasets.forEach((ds) => {
            const card = document.createElement('div');
            card.className = 'chart-card drop-zone';
            card.id = `card_${ds.id}`;
            card.setAttribute('data-chart-id', ds.id);

            // Permite maximizar manual usando la clase de grid CSS
            if (maximizedChartIds.has(ds.id)) {
                card.classList.add('full-width');
            }

            // Construcción del Header interactivo
            const header = document.createElement('div');
            header.className = 'card-header';

            const handle = document.createElement('div');
            handle.className = 'drag-handle';
            handle.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>`;
            handle.title = "Arrastra para reordenar gráficas";

            const title = document.createElement('h3');
            title.className = 'card-title';
            title.textContent = ds.title;

            // Contenedor de Botones (Cerrar / Expandir)
            const controls = document.createElement('div');
            controls.className = 'card-controls';

            const maxBtn = document.createElement('button');
            maxBtn.className = 'action-chart-btn';
            if (maximizedChartIds.has(ds.id)) {
                maxBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"></path></svg>`;
                maxBtn.title = "Restaurar tamaño normal";
            } else {
                maxBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg>`;
                maxBtn.title = "Expandir todo el ancho";
            }
            maxBtn.onclick = () => {
                if (maximizedChartIds.has(ds.id)) {
                    maximizedChartIds.delete(ds.id);
                } else {
                    maximizedChartIds.add(ds.id);
                }
                updateUI();
            };

            const closeBtn = document.createElement('button');
            closeBtn.className = 'action-chart-btn close-btn';
            closeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"></path></svg>`;
            closeBtn.title = "Ocultar gráfica";
            closeBtn.onclick = () => {
                hiddenChartIds.add(ds.id);
                maximizedChartIds.delete(ds.id);
                updateUI();
            };

            controls.appendChild(maxBtn);
            controls.appendChild(closeBtn);

            header.appendChild(handle);
            header.appendChild(title);
            header.appendChild(controls);

            const canvasWrapper = document.createElement('div');
            canvasWrapper.className = 'canvas-wrapper';
            canvasWrapper.style.display = 'block';

            const canvas = document.createElement('canvas');
            canvas.id = ds.id;

            canvasWrapper.appendChild(canvas);
            card.appendChild(header);
            card.appendChild(canvasWrapper);
            grid.appendChild(card);

            // Reordenamiento local mediante Drag Handle (Manija)
            card.draggable = false; // Por defecto NO se arrastra (protegiendo el canvas)

            // Activa draggability SOLO si el mouse agarra la zona de control
            handle.addEventListener('mouseenter', () => card.draggable = true);
            handle.addEventListener('mouseleave', () => {
                if (!card.classList.contains('dragging-card')) {
                    card.draggable = false;
                }
            });

            card.addEventListener('dragstart', (e) => {
                card.classList.add('dragging-card');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('source-chart-id', ds.id);
            });
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging-card');
                card.draggable = false;
            });

            attachDropEvents(card);
            renderSingleChart(ds.id, ds.labels, ds.values, ds.recommendedType);
        });

        attachGridRestoreDropEvent(grid);
    }

    function renderSingleChart(canvasId, labels, dataValues, type) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        if (chartInstances[canvasId]) chartInstances[canvasId].destroy();

        const totalSum = dataValues.reduce((a, b) => a + Number(b), 0);

        chartInstances[canvasId] = new Chart(ctx, {
            type: type,
            data: {
                labels: labels,
                datasets: [{
                    label: 'Registros',
                    data: dataValues,
                    backgroundColor: ['rgba(59, 130, 246, 0.8)', 'rgba(16, 185, 129, 0.8)', 'rgba(245, 158, 11, 0.8)', 'rgba(217, 70, 239, 0.8)', 'rgba(239, 68, 68, 0.8)', 'rgba(14, 165, 233, 0.8)', 'rgba(244, 63, 94, 0.8)'],
                    borderColor: ['#2563eb', '#059669', '#d97706', '#c026d3', '#dc2626', '#0284c7', '#e11d48'],
                    borderWidth: 1,
                    hoverOffset: 6,
                    borderRadius: (type === 'bar') ? 6 : 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 20 } },
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#e2e8f0', font: { family: "'Inter', sans-serif" } } },
                    tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.9)', titleFont: { family: "'Inter', sans-serif" }, bodyFont: { family: "'Inter', sans-serif" }, padding: 12, cornerRadius: 8, borderColor: 'rgba(51, 65, 85, 0.5)', borderWidth: 1 },
                    datalabels: {
                        color: (context) => {
                            return (type === 'pie' || type === 'doughnut') ? '#ffffff' : '#f8fafc';
                        },
                        anchor: type === 'bar' ? 'end' : 'center',
                        align: type === 'bar' ? 'end' : 'center',
                        formatter: (value) => {
                            if (totalSum === 0) return value;
                            let percentage = ((value * 100) / totalSum).toFixed(1) + "%";
                            return `${value}\n(${percentage})`;
                        },
                        font: { weight: '600', size: 11, family: "'Inter', sans-serif" },
                        textStrokeColor: 'rgba(0,0,0,0.5)',
                        textStrokeWidth: (type === 'pie' || type === 'doughnut') ? 2 : 0,
                    }
                },
                scales: (type === 'bar' || type === 'line') ? {
                    y: { beginAtZero: true, grid: { color: 'rgba(51, 65, 85, 0.1)' }, ticks: { color: '#94a3b8', font: { family: "'Inter', sans-serif" } } },
                    x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { family: "'Inter', sans-serif" } } }
                } : {
                    y: { display: false }, x: { display: false }
                }
            }
        });
    }

    // --- 6. Logica de Eventos Múltiples D&D ---
    const draggables = document.querySelectorAll('.chart-type-item');

    draggables.forEach(draggable => {
        draggable.addEventListener('dragstart', () => {
            draggable.classList.add('dragging');
            draggable.setAttribute('data-dragging-type', 'true');
        });

        draggable.addEventListener('dragend', () => {
            draggable.classList.remove('dragging');
            draggable.removeAttribute('data-dragging-type');
        });
    });

    function attachDropEvents(dropZone) {
        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            // Controla estilos solo si se está arrastrando algo válido hacia esta tarjeta
            if (document.querySelector('.chart-type-item.dragging') || document.querySelector('.chart-card.dragging-card')) {
                dropZone.classList.add('drag-over');
            }
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');

            // Revisa si es un ítem de tipo de gráfica
            const draggedType = document.querySelector('.chart-type-item.dragging');
            if (draggedType) {
                const newType = draggedType.getAttribute('data-type');
                const uniqueTargetId = dropZone.getAttribute('data-chart-id');
                const datasetToUpdate = currentDataSets.find(d => d.id === uniqueTargetId);

                if (datasetToUpdate) {
                    datasetToUpdate.recommendedType = newType;
                    renderSingleChart(datasetToUpdate.id, datasetToUpdate.labels, datasetToUpdate.values, datasetToUpdate.recommendedType);
                }
                return;
            }

            // Revisa si es un reordenamiento posicional (Sortable Cards)
            const draggedCard = document.querySelector('.chart-card.dragging-card');
            if (draggedCard && draggedCard !== dropZone) {
                const sourceId = draggedCard.getAttribute('data-chart-id');
                const targetId = dropZone.getAttribute('data-chart-id');

                const sourceIndex = allChartDatasets.findIndex(d => d.id === sourceId);
                const targetIndex = allChartDatasets.findIndex(d => d.id === targetId);

                if (sourceIndex !== -1 && targetIndex !== -1) {
                    // Splice quita la tarjeta arrastrada, y luego la inserta en su nuevo índice
                    const [movedItem] = allChartDatasets.splice(sourceIndex, 1);
                    allChartDatasets.splice(targetIndex, 0, movedItem);
                    updateUI(); // Se repinta todo con las nuevas posiciones
                }
            }
        });
    }

    function attachGridRestoreDropEvent(grid) {
        grid.addEventListener('dragover', e => {
            if (document.querySelector('[data-dragging-hidden="true"]')) {
                e.preventDefault();
            }
        });

        grid.addEventListener('drop', e => {
            const hiddenItem = document.querySelector('[data-dragging-hidden="true"]');
            if (hiddenItem) {
                e.preventDefault();
                const restoreId = hiddenItem.getAttribute('data-restore-id');
                if (restoreId) {
                    hiddenChartIds.delete(restoreId);
                    updateUI();
                }
            }
        });
    }

    // --- Arranque inicial ---
    loadBranches();
});
