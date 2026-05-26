// worker.js - Procesador en segundo plano para no bloquear la interfaz.
function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeJsString(value) {
    return String(value ?? "").replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}

onmessage = function(e) {
    const rawData = e.data;
    let htmlResult = "";

    if (!rawData.recommendations || rawData.recommendations.length === 0) {
        htmlResult = "<p style='color: var(--text-muted);'>No encontramos recomendaciones por ahora. Dale me gusta a algunas canciones o vuelve a elegir tus preferencias.</p>";
    } else {
        rawData.recommendations.forEach(track => {
            const trackId = escapeJsString(track.track_id);
            const score100 = Math.round(Number(track.score || 0) * 100);

            htmlResult += `
                <div class="track-card">
                    <div class="track-header">
                        <div class="track-info">
                            <h3>${escapeHtml(track.titulo)}</h3>
                            <p>${escapeHtml(track.artista)} &middot; ${escapeHtml(track.genero)}</p>
                        </div>
                        <div class="score-badge">${score100}/100</div>
                    </div>

                    <div class="reason-box">
                        <span>✨ IA:</span> ${escapeHtml(track.reason)}
                    </div>

                    <div class="button-row">
                        <button class="btn-like" onclick="registrarInteraccion('${trackId}', 5)">
                            ❤ Me gusta
                        </button>
                        <button class="btn-secondary" onclick="registrarInteraccion('${trackId}', 1)">
                            Omitir
                        </button>
                    </div>
                </div>
            `;
        });
    }
    postMessage(htmlResult);
};
