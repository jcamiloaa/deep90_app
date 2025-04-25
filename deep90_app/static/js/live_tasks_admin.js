/**
 * JavaScript para manejar interacciones en la interfaz admin de tareas en vivo
 */
(function($) {
    'use strict';
    
    // Ejecutar cuando el DOM esté completamente cargado
    $(document).ready(function() {
        // Agregar botones de acción a cada fila de la tabla de tareas
        addActionButtonsToTable();
        
        // Configurar intervalos para auto-recargar la página
        setupAutoRefresh();
    });
    
    /**
     * Agrega botones de acción para activar/desactivar y reiniciar tareas en la interfaz de administración
     */
    function addActionButtonsToTable() {
        // Obtener el tipo de tarea de la URL
        const urlParts = window.location.pathname.split('/');
        const modelName = urlParts[urlParts.indexOf('sports_data') + 1];
        let taskType = '';
        
        if (modelName === 'livefixturedata') {
            return; // No agregar botones a la vista de datos en vivo
        } else if (modelName === 'livefixturedata') {
            return; // No agregar botones a la vista de datos de cuotas
        } else if (modelName === 'livefixturtask') {
            taskType = 'fixture';
        } else if (modelName === 'liveoddsdata') {
            taskType = 'odds';
        }
        
        // Si estamos en una vista de cambio o detalle, no continuar
        if (window.location.pathname.indexOf('change') > -1 || window.location.pathname.indexOf('add') > -1) {
            return;
        }
        
        // Manejar vista de lista
        const table = $('#result_list');
        if (table.length === 0) return;
        
        // Agregar columna de acciones al encabezado de la tabla
        const headerRow = table.find('thead tr');
        headerRow.append('<th scope="col" class="column-actions">Acciones</th>');
        
        // Para cada fila de datos, agregar botones de acción
        table.find('tbody tr').each(function() {
            const row = $(this);
            const cells = row.find('td');
            if (cells.length === 0) return;
            
            // Obtener el ID de la tarea de la primera columna (asumiendo que contiene el ID como enlace)
            const firstCell = cells.first();
            const taskLink = firstCell.find('a').attr('href');
            if (!taskLink) return;
            
            const taskId = taskLink.split('/').filter(Boolean).pop();
            if (!taskId || isNaN(parseInt(taskId))) return;
            
            // Obtener estado actual para determinar qué botones mostrar
            const statusText = $(cells[1]).text().toLowerCase();
            const isEnabled = statusText.indexOf('✓') > -1;
            const isFailed = statusText.indexOf('fall') > -1; // "fallido" en español
            
            // Crear celda de acciones
            const actionsCell = $('<td class="action-buttons"></td>');
            
            // Botón activar/desactivar
            const toggleButton = $('<button class="button"></button>')
                .text(isEnabled ? 'Desactivar' : 'Activar')
                .addClass(isEnabled ? 'default' : 'primary')
                .attr('title', isEnabled ? 'Desactivar esta tarea' : 'Activar esta tarea')
                .css('margin-right', '5px')
                .on('click', function(e) {
                    e.preventDefault();
                    toggleTaskStatus(taskId, $(this), taskType);
                });
            
            // Botón reiniciar (solo para tareas fallidas)
            let restartButton;
            if (isFailed) {
                restartButton = $('<button class="button warning"></button>')
                    .text('Reiniciar')
                    .attr('title', 'Reiniciar la tarea fallida')
                    .on('click', function(e) {
                        e.preventDefault();
                        restartTask(taskId, $(this), taskType);
                    });
                actionsCell.append(restartButton);
            }
            
            // Añadir botones a la celda
            actionsCell.append(toggleButton);
            if (restartButton) {
                actionsCell.append(restartButton);
            }
            
            // Añadir celda a la fila
            row.append(actionsCell);
        });
    }
    
    /**
     * Cambia el estado de activación de una tarea
     */
    function toggleTaskStatus(taskId, buttonElement, taskType) {
        // Deshabilitar el botón durante la petición
        buttonElement.prop('disabled', true).text('Procesando...');
        
        // Construir URL para la petición
        const url = window.location.pathname.replace(/\/$/, '') + '/toggle-status/' + taskId + '/';
        
        // Realizar petición AJAX
        $.ajax({
            url: url,
            type: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()
            },
            success: function(data) {
                if (data.success) {
                    // Recargar la página para mostrar los cambios
                    window.location.reload();
                } else {
                    alert('Error: ' + data.message);
                    buttonElement.prop('disabled', false).text('Reintentar');
                }
            },
            error: function(xhr, status, error) {
                alert('Error en la petición: ' + error);
                buttonElement.prop('disabled', false).text('Reintentar');
            }
        });
    }
    
    /**
     * Reinicia una tarea fallida
     */
    function restartTask(taskId, buttonElement, taskType) {
        // Deshabilitar el botón durante la petición
        buttonElement.prop('disabled', true).text('Procesando...');
        
        // Construir URL para la petición
        const url = window.location.pathname.replace(/\/$/, '') + '/restart-task/' + taskId + '/';
        
        // Realizar petición AJAX
        $.ajax({
            url: url,
            type: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()
            },
            success: function(data) {
                if (data.success) {
                    // Recargar la página para mostrar los cambios
                    window.location.reload();
                } else {
                    alert('Error: ' + data.message);
                    buttonElement.prop('disabled', false).text('Reintentar');
                }
            },
            error: function(xhr, status, error) {
                alert('Error en la petición: ' + error);
                buttonElement.prop('disabled', false).text('Reintentar');
            }
        });
    }
    
    /**
     * Configura el intervalo para auto-recargar la página si estamos en datos en vivo
     */
    function setupAutoRefresh() {
        const urlParts = window.location.pathname.split('/');
        const modelName = urlParts[urlParts.indexOf('sports_data') + 1];
        
        // Solo aplicar auto-recarga a las vistas de datos en vivo
        if (modelName === 'livefixturedata' || modelName === 'liveoddsdata') {
            // Añadir control de auto-recarga en la parte superior de la página
            const refreshControl = $('<div class="auto-refresh-control"></div>')
                .css({
                    'padding': '10px',
                    'background-color': '#f8f9fa',
                    'border': '1px solid #dee2e6',
                    'border-radius': '4px',
                    'margin-bottom': '15px',
                    'display': 'flex',
                    'align-items': 'center',
                    'justify-content': 'space-between'
                });
            
            const statusSpan = $('<span class="auto-refresh-status">Auto-recarga activada</span>');
            
            const controls = $('<div></div>');
            
            const intervalSelect = $('<select id="refresh-interval"></select>')
                .append('<option value="5">5 segundos</option>')
                .append('<option value="10">10 segundos</option>')
                .append('<option value="30" selected>30 segundos</option>')
                .append('<option value="60">1 minuto</option>')
                .css('margin-right', '10px');
            
            const toggleButton = $('<button class="button primary">Desactivar</button>')
                .on('click', function() {
                    toggleAutoRefresh($(this), statusSpan);
                });
            
            controls.append(intervalSelect).append(toggleButton);
            refreshControl.append(statusSpan).append(controls);
            
            // Insertar el control después del título de la página
            $('.breadcrumbs').after(refreshControl);
            
            // Iniciar el intervalo de auto-recarga
            let intervalId = setInterval(function() {
                window.location.reload();
            }, 30000); // 30 segundos por defecto
            
            // Guardar el ID del intervalo
            $('body').data('autoRefreshInterval', intervalId);
            
            // Configurar cambio de intervalo
            intervalSelect.on('change', function() {
                const selectedInterval = $(this).val() * 1000; // Convertir a milisegundos
                clearInterval($('body').data('autoRefreshInterval'));
                
                // Solo crear nuevo intervalo si auto-recarga está activada
                if (toggleButton.text() === 'Desactivar') {
                    intervalId = setInterval(function() {
                        window.location.reload();
                    }, selectedInterval);
                    $('body').data('autoRefreshInterval', intervalId);
                }
            });
        }
    }
    
    /**
     * Activa o desactiva la auto-recarga
     */
    function toggleAutoRefresh(buttonElement, statusSpan) {
        if (buttonElement.text() === 'Desactivar') {
            clearInterval($('body').data('autoRefreshInterval'));
            buttonElement.text('Activar').removeClass('primary').addClass('default');
            statusSpan.text('Auto-recarga desactivada');
        } else {
            const intervalSelect = $('#refresh-interval');
            const selectedInterval = intervalSelect.val() * 1000; // Convertir a milisegundos
            
            const intervalId = setInterval(function() {
                window.location.reload();
            }, selectedInterval);
            
            $('body').data('autoRefreshInterval', intervalId);
            buttonElement.text('Desactivar').removeClass('default').addClass('primary');
            statusSpan.text('Auto-recarga activada');
        }
    }
    
    /**
     * Obtiene el token CSRF de las cookies
     */
    function getCSRFToken() {
        let csrfToken = null;
        
        // Buscar token CSRF en las cookies
        if (document.cookie) {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.startsWith('csrftoken=')) {
                    csrfToken = cookie.substring('csrftoken='.length);
                    break;
                }
            }
        }
        
        return csrfToken;
    }
    
})(window.django ? django.jQuery : jQuery);