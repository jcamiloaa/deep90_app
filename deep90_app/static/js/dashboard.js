// Dashboard JS para Deep90 Admin

document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM
    const sidebarToggleBtn = document.getElementById('sidebar-toggle');
    const themeToggleBtn = document.getElementById('theme-toggle');
    const body = document.body;
    
    // Inicializar estado del tema desde localStorage
    if (localStorage.getItem('darkMode') === 'enabled') {
        body.classList.add('dark-theme');
        updateThemeIcon(true);
    }
    
    // Inicializar estado de la barra lateral desde localStorage
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        body.classList.add('sidebar-collapsed');
        updateSidebarIcon(true);
    }
    
    // Evento para alternar la barra lateral
    sidebarToggleBtn.addEventListener('click', function() {
        const isCollapsed = body.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
        updateSidebarIcon(isCollapsed);
    });
    
    // Evento para alternar el tema oscuro/claro
    themeToggleBtn.addEventListener('click', function() {
        const isDarkMode = body.classList.toggle('dark-theme');
        localStorage.setItem('darkMode', isDarkMode ? 'enabled' : 'disabled');
        updateThemeIcon(isDarkMode);
    });
    
    // Actualizar icono del botón de tema
    function updateThemeIcon(isDarkMode) {
        const icon = themeToggleBtn.querySelector('i');
        if (isDarkMode) {
            icon.classList.replace('fa-moon', 'fa-sun');
            themeToggleBtn.setAttribute('title', 'Cambiar a modo claro');
        } else {
            icon.classList.replace('fa-sun', 'fa-moon');
            themeToggleBtn.setAttribute('title', 'Cambiar a modo oscuro');
        }
    }
    
    // Actualizar icono del botón de barra lateral
    function updateSidebarIcon(isCollapsed) {
        const icon = sidebarToggleBtn.querySelector('i');
        if (isCollapsed) {
            icon.classList.replace('fa-times', 'fa-bars');
            sidebarToggleBtn.setAttribute('title', 'Expandir menú lateral');
        } else {
            icon.classList.replace('fa-bars', 'fa-times');
            sidebarToggleBtn.setAttribute('title', 'Colapsar menú lateral');
        }
    }
    
    // En pantallas pequeñas, colapsar la barra lateral al hacer clic fuera de ella
    document.addEventListener('click', function(event) {
        const windowWidth = window.innerWidth;
        if (windowWidth <= 768 && !event.target.closest('.sidebar') && 
            !event.target.closest('#sidebar-toggle') && 
            body.classList.contains('sidebar-visible')) {
            body.classList.remove('sidebar-visible');
        }
    });
    
    // En pantallas pequeñas, mostrar/ocultar barra lateral
    if (window.innerWidth <= 768) {
        sidebarToggleBtn.addEventListener('click', function(event) {
            event.stopPropagation();
            body.classList.toggle('sidebar-visible');
        });
    }
});