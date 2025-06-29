// frontend/js/main.js

// Garante que o config.js foi carregado
if (typeof config === 'undefined') {
    console.error("Erro: config.js não foi carregado. Verifique o caminho no index.html.");
}

// 1. Inicializa o mapa Leaflet
const map = L.map('map').setView([config.centerLat, config.centerLon], config.defaultZoom);

// 2. Adiciona a camada base do OpenStreetMap
L.tileLayer(config.osmTileUrl, {
    attribution: config.osmAttribution,
    maxZoom: 19,
}).addTo(map);

// 3. Função para obter a cor do marcador baseada no score de prioridade
function getPriorityColor(score) {
    if (score >= 5) {
        return 'red';      // Alta prioridade (vermelho)
    } else if (score >= 2) {
        return 'orange';   // Média prioridade (laranja)
    } else {
        return 'green';    // Baixa prioridade (verde)
    }
}

// 4. Função para estilo dos pontos (círculos coloridos)
function stylePoints(feature) {
    const score = feature.properties.prioridade_score || 0; // Pega o score, default 0
    return {
        radius: 8,
        fillColor: getPriorityColor(score),
        color: '#000',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}

// 5. Função para o popup ao clicar no ponto
function onEachFeature(feature, layer) {
    if (feature.properties) {
        const props = feature.properties;
        let popupContent = `
            <b>Tipo:</b> ${props.tipo_vazamento || 'N/A'}<br>
            <b>Descrição:</b> ${props.descricao_detalhes || 'N/A'}<br>
            <b>Intensidade:</b> ${props.intensidade_vazamento || 'N/A'}<br>
            <b>Origem:</b> ${props.origem_vazamento || 'N/A'}<br>
            <b>Prioridade:</b> ${props.prioridade_score || 0}<br>
            <b>Status:</b> ${props.status || 'N/A'}<br>
            <b>Reportado em:</b> ${new Date(props.data_submissao).toLocaleString()}<br>
        `;
        if (props.foto_url) {
            popupContent += `<img src="${props.foto_url}" alt="Foto do Vazamento" style="max-width:200px; height:auto; margin-top: 10px;">`;
        }
        layer.bindPopup(popupContent);
    }
}

// 6. Carrega os dados de vazamentos via WFS (Web Feature Service)
fetch(config.wfsServiceUrl)
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        L.geoJSON(data, {
            pointToLayer: function (feature, latlng) {
                // Cria um círculo para cada ponto
                return L.circleMarker(latlng, stylePoints(feature));
            },
            onEachFeature: onEachFeature
        }).addTo(map);
        console.log("Dados de vazamentos carregados com sucesso.");
    })
    .catch(error => {
        console.error("Erro ao carregar dados WFS:", error);
        alert("Não foi possível carregar os dados de vazamentos. Verifique a URL do WFS e o servidor.");
    });