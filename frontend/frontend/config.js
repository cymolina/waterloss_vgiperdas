// frontend/config.js
const config = {
    // URL base para os tiles do OpenStreetMap (ex: OpenStreetMap ou CartoDB)
    osmTileUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    osmAttribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',

    // URL do seu QGIS Server ou GeoNode para o serviço WFS (Web Feature Service)
    // Este serviço WFS deve expor a camada 'vazamentos_denuncias' do seu PostGIS
    // Exemplo: 'http://localhost:8080/qgis/qgis_server.fcgi?MAP=caminho_para_seu_projeto_qgis.qgz&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=vazamentos_denuncias&OUTPUTFORMAT=application/json'
    // Você precisará configurar o QGIS Server para publicar seu projeto QGIS que contém a camada vazamentos_denuncias.
    wfsServiceUrl: 'http://localhost:8080/qgis/qgis_server.fcgi?MAP=/path/to/your/qgis_project.qgz&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=vazamentos_denuncias&OUTPUTFORMAT=application/json',

    // Coordenadas centrais para o mapa (ex: centro de São Paulo)
    centerLat: -23.5505, // Latitude de São Paulo
    centerLon: -46.6333, // Longitude de São Paulo
    defaultZoom: 12
};