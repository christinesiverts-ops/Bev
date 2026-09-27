// Store map + route planning (Leaflet). Loaded only on /map and /routes/{id}.
(function () {
  "use strict";
  const cfgEl = document.getElementById("map-config");
  if (!cfgEl || !window.L) return;
  const cfg = JSON.parse(cfgEl.textContent);
  const css = (name) => "rgb(" + getComputedStyle(document.documentElement).getPropertyValue("--" + name).trim().split(/\s+/).join(",") + ")";
  const COLORS = { urgent: css("danger"), due: css("warning"), ok: css("success"), primary: css("primary") };
  const map = L.map("map", { zoomControl: true, scrollWheelZoom: true }).setView([45.5, -122.6], 7);
  L.tileLayer(cfg.tiles.url, { maxZoom: 19, attribution: cfg.tiles.attribution }).addTo(map);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  function locate(cb) {
    if (!("geolocation" in navigator)) return cb(null);
    navigator.geolocation.getCurrentPosition((p) => cb([p.coords.latitude, p.coords.longitude]), () => cb(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 120000 });
  }
  let meMarker = null;
  function showMe(ll) {
    if (!ll) return;
    if (meMarker) meMarker.setLatLng(ll);
    else meMarker = L.circleMarker(ll, { radius: 8, color: "#fff", weight: 3, fillColor: "#2F6FEB", fillOpacity: 1 })
      .addTo(map).bindTooltip("You are here");
  }

  // ---------------- plan mode: all stores ----------------
  if (cfg.mode === "plan") {
    const list = document.querySelector("[data-store-list]");
    const form = document.querySelector("[data-plan-form]");
    const selected = new Set();
    let stores = [], markers = {}, filter = "all", chain = "", q = "";
    const levelRank = { urgent: 0, due: 1, ok: 2 };

    function visible(s) {
      if (chain && s.chain !== chain) return false;
      if (q && !(s.label + " " + s.address).toLowerCase().includes(q)) return false;
      if (filter === "attention") return s.level !== "ok";
      if (filter === "urgent") return s.level === "urgent";
      return true;
    }
    function syncForm() {
      if (!form) return;
      const box = form.querySelector("[data-selected-inputs]");
      box.innerHTML = "";
      selected.forEach((id) => { const i = el("input"); i.type = "hidden"; i.name = "store_id"; i.value = id; box.appendChild(i); });
      form.querySelector("[data-selected-count]").textContent = selected.size;
      form.querySelector("[data-plan-btn]").disabled = selected.size === 0;
    }
    function toggle(id, on) {
      if (on === undefined) on = !selected.has(id);
      on ? selected.add(id) : selected.delete(id);
      const m = markers[id];
      if (m) m.setStyle({ weight: on ? 4 : 2, color: on ? COLORS.primary : "#fff", radius: on ? 10 : 8 });
      const cb = list.querySelector('input[data-id="' + id + '"]');
      if (cb) cb.checked = on;
      syncForm();
    }
    function render() {
      list.innerHTML = "";
      const shown = stores.filter(visible).sort((a, b) => levelRank[a.level] - levelRank[b.level] || a.label.localeCompare(b.label));
      if (!shown.length) { list.appendChild(el("p", "hint p-4", stores.length ? "No stores match." : "No stores yet. Import a store list first.")); }
      shown.forEach((s) => {
        const row = el("label", "flex cursor-pointer items-start gap-3 border-b border-border px-4 py-3 hover:bg-raised");
        const cb = el("input"); cb.type = "checkbox"; cb.className = "mt-1 size-4 shrink-0"; cb.dataset.id = s.id; cb.checked = selected.has(s.id);
        cb.addEventListener("change", () => toggle(s.id, cb.checked));
        const dot = el("span", "mt-1.5 size-2.5 shrink-0 rounded-full " + (s.level === "urgent" ? "bg-danger" : s.level === "due" ? "bg-warning" : "bg-success"));
        const body = el("span", "min-w-0 flex-1");
        body.appendChild(el("span", "block truncate text-sm font-semibold", s.label));
        body.appendChild(el("span", "hint block truncate", s.reasons.length ? s.reasons.join(" · ") : ("Last visit " + (s.last || "never"))));
        if (s.lat == null) body.appendChild(el("span", "block text-xs text-warning", "Not on map yet"));
        const go = el("a", "shrink-0 text-xs font-semibold", "View"); go.href = "/stores/" + s.id;
        go.addEventListener("click", (e) => e.stopPropagation());
        row.append(cb, dot, body, go);
        row.addEventListener("mouseenter", () => markers[s.id] && markers[s.id].openTooltip());
        row.addEventListener("mouseleave", () => markers[s.id] && markers[s.id].closeTooltip());
        list.appendChild(row);
      });
      Object.values(markers).forEach((m) => {
        const s = m.options.store;
        visible(s) ? m.addTo(map) : m.remove();
      });
    }
    fetch("/map/stores.json", { credentials: "same-origin" }).then((r) => r.json()).then((data) => {
      stores = data;
      const bounds = [];
      data.forEach((s) => {
        if (s.lat == null) return;
        const m = L.circleMarker([s.lat, s.lng], { radius: 8, weight: 2, color: "#fff", fillColor: COLORS[s.level], fillOpacity: 0.95, store: s });
        m.bindTooltip(s.label + (s.reasons.length ? " · " + s.reasons[0] : ""));
        m.on("click", () => toggle(s.id));
        markers[s.id] = m; bounds.push([s.lat, s.lng]);
      });
      if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
      render();
    });
    document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
      filter = b.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      render();
    }));
    const chainSel = document.querySelector("[data-chain]"); if (chainSel) chainSel.addEventListener("change", () => { chain = chainSel.value; render(); });
    const search = document.querySelector("[data-search]"); if (search) search.addEventListener("input", () => { q = search.value.toLowerCase(); render(); });
    const selDue = document.querySelector("[data-select-attention]");
    if (selDue) selDue.addEventListener("click", () => stores.filter((s) => visible(s) && s.level !== "ok").forEach((s) => toggle(s.id, true)));
    const clear = document.querySelector("[data-clear]");
    if (clear) clear.addEventListener("click", () => Array.from(selected).forEach((id) => toggle(id, false)));
    locate((ll) => {
      showMe(ll);
      const fromHere = form && form.querySelector("[data-from-here]");
      if (ll && fromHere) { form.start_lat.value = ll[0].toFixed(6); form.start_lng.value = ll[1].toFixed(6); }
      const apply = () => {
        form.start_lat.value = fromHere.checked && ll ? ll[0].toFixed(6) : "";
        form.start_lng.value = fromHere.checked && ll ? ll[1].toFixed(6) : "";
      };
      if (fromHere) fromHere.addEventListener("change", apply);
      // planning for someone else: don't start from the manager's location
      const who = form && form.querySelector("select[name=assignee_id]");
      if (who && fromHere) who.addEventListener("change", () => {
        fromHere.checked = who.value === form.dataset.self; apply();
      });
    });
  }

  // ---------------- route mode: one route ----------------
  if (cfg.mode === "route") {
    const pts = [];
    if (cfg.start) {
      L.circleMarker(cfg.start, { radius: 7, color: "#fff", weight: 2, fillColor: "#2F6FEB", fillOpacity: 1 }).addTo(map).bindTooltip("Start");
      pts.push(cfg.start);
    }
    cfg.stops.forEach((s) => {
      if (s.lat == null) return;
      const icon = L.divIcon({ className: "route-pin" + (s.done ? " done" : ""), html: "", iconSize: [30, 30], iconAnchor: [15, 15] });
      const mk = L.marker([s.lat, s.lng], { icon, title: s.label }).addTo(map).bindTooltip(s.n + ". " + s.label);
      mk.on("add", () => { const e = mk.getElement(); if (e) e.textContent = s.done ? "✓" : String(s.n); });
      if (mk.getElement()) mk.getElement().textContent = s.done ? "✓" : String(s.n);
      pts.push([s.lat, s.lng]);
    });
    if (pts.length > 1) L.polyline(pts, { color: COLORS.primary, weight: 4, opacity: 0.75, dashArray: "8 8" }).addTo(map);
    if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 14 });
    locate(showMe);
    const re = document.querySelector("[data-reoptimize]");
    if (re) re.addEventListener("submit", (e) => {
      if (re.dataset.ready) return;
      e.preventDefault();
      locate((ll) => { if (ll) { re.lat.value = ll[0].toFixed(6); re.lng.value = ll[1].toFixed(6); } re.dataset.ready = "1"; re.requestSubmit(); });
    });
  }
})();
