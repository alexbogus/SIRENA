// Utilidades compartidas por las tablas de histórico de mensajes: la de
// cada card de altavoz en dashboard.html y la de página completa en
// message_history.html. Antes vivían duplicadas casi al carácter en ambas
// plantillas.

function deliveryBadge(status) {
    if (status === "confirmed") return `<span class="text-emerald-400 inline-flex items-center gap-1"><i data-lucide="check" class="w-3 h-3"></i>confirmado</span>`;
    if (status === "unconfirmed") return `<span class="text-red-400 inline-flex items-center gap-1"><i data-lucide="x" class="w-3 h-3"></i>no confirmado</span>`;
    return `<span class="text-slate-500 inline-flex items-center gap-1"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>verificando</span>`;
}

// Parser de "DD/MM/YYYY - HH:MM:ss" a valor comparable, para poder ordenar
// por fecha real y no alfabéticamente (que daría un orden erróneo).
function parseEsDate(s) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4}) - (\d{2}):(\d{2}):(\d{2})$/.exec(s || "");
    if (!m) return 0;
    return new Date(m[3], m[2] - 1, m[1], m[4], m[5], m[6]).getTime();
}

function sortHistory(entries, col, dir) {
    const sorted = [...entries];
    sorted.sort((a, b) => {
        let av = a[col], bv = b[col];
        if (col.endsWith("_at")) { av = parseEsDate(av); bv = parseEsDate(bv); }
        else if (typeof av === "number" || typeof bv === "number") { av = av || 0; bv = bv || 0; }
        else { av = (av || "").toLowerCase(); bv = (bv || "").toLowerCase(); }
        if (av < bv) return dir === "asc" ? -1 : 1;
        if (av > bv) return dir === "asc" ? 1 : -1;
        return 0;
    });
    return sorted;
}
