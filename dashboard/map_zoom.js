
(function () {

    const GRAPH_ID = "territorial-map";

    // Nivel mínimo de zoom permitido.
    const MIN_ZOOM = 9.5;

    let configuredMap = null;

    function configureMapZoom() {

        const container = document.getElementById(GRAPH_ID);

        if (!container) return;

        const plot = container.querySelector(".js-plotly-plot");

        if (!plot || !plot._fullLayout) return;

        // Obtener la instancia interna de MapLibre.
        const mapLayout = plot._fullLayout.map;

        const mapInstance = mapLayout?._subplot?.map;

        if (!mapInstance) return;

        // Evitar configurar varias veces la misma instancia.
        if (configuredMap === mapInstance) return;

        configuredMap = mapInstance;

        // Establecer el límite nativo de alejamiento.
        mapInstance.setMinZoom(MIN_ZOOM);

        console.log(
            "[MapZoom] Límite nativo configurado:",
            MIN_ZOOM
        );

    }

    // Detectar creación y actualización del mapa.
    const observer = new MutationObserver(configureMapZoom);

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Comprobar cuando Plotly termina de dibujar.
    document.addEventListener("DOMContentLoaded", configureMapZoom);

    configureMapZoom();

})();
