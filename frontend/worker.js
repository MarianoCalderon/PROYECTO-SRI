// worker.js - Procesador en segundo plano
onmessage = function(e) {
    const rawData = e.data;
    let htmlResult = "";
    
    if (!rawData.recommendations || rawData.recommendations.length === 0) {
        htmlResult = "<p style='color: var(--text-muted);'>No encontramos recomendaciones. ¡Intenta interactuar más!</p>";
    } else {
        rawData.recommendations.forEach(track => {
            // Generación de tarjetas con la nueva estructura CSS chic
            htmlResult += `
                <div class="track-card">
                    <div class="track-header">
                        <div class="track-info">
                            <h3>${track.titulo}</h3>
                            <p>${track.artista} &middot; ${track.genero}</p>
                        </div>
                        <button class="btn-like" onclick="registrarInteraccion('${track.track_id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style="vertical-align: text-bottom;">
                              <path fill-rule="evenodd" d="M8 1.314C12.438-3.248 23.534 4.735 8 15-7.534 4.736 3.562-3.248 8 1.314z"/>
                            </svg>
                        </button>
                    </div>
                    <div class="reason-box">
                        <span>✨ IA:</span> ${track.reason}
                    </div>
                </div>
            `;
        });
    }
    postMessage(htmlResult);
}