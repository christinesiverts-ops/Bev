// Chain Audit - progressive enhancements only; every page works without JS.
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // auto-submit filter controls
  $$("[data-autosubmit]").forEach((el) => el.addEventListener("change", () => el.form && el.form.submit()));

  // confirmations + double-submit guard
  $$("form").forEach((f) => {
    f.addEventListener("submit", (e) => {
      const msg = f.getAttribute("data-confirm");
      if (msg && !window.confirm(msg)) { e.preventDefault(); return; }
      if (f.method.toLowerCase() === "post") {
        setTimeout(() => $$("button", f).forEach((b) => { b.disabled = true; }), 0);
      }
    });
  });

  $$("[data-back]").forEach((a) => a.addEventListener("click", (e) => {
    if (history.length > 1) { e.preventDefault(); history.back(); }
  }));

  // GPS on check-in
  const checkin = $("#checkin-form");
  if (checkin) {
    const status = $("[data-gps-status]", checkin);
    if (!("geolocation" in navigator)) {
      status.textContent = "This browser can't share location. You can still check in.";
    } else {
      navigator.geolocation.getCurrentPosition((pos) => {
        checkin.lat.value = pos.coords.latitude.toFixed(6);
        checkin.lng.value = pos.coords.longitude.toFixed(6);
        checkin.accuracy.value = Math.round(pos.coords.accuracy);
        status.textContent = "Location captured (±" + Math.round(pos.coords.accuracy) + " m).";
        status.className = "small ok-text";
      }, () => {
        status.textContent = "Location not shared. Your check-in will show \"No GPS\".";
        status.className = "small warn-text";
      }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    }
  }

  // fill lat/lng on the store form
  $$("[data-fill-gps]").forEach((btn) => btn.addEventListener("click", () => {
    const f = btn.form;
    navigator.geolocation && navigator.geolocation.getCurrentPosition((pos) => {
      f.lat.value = pos.coords.latitude.toFixed(6);
      f.lng.value = pos.coords.longitude.toFixed(6);
    }, () => alert("Couldn't get your location."));
  }));

  // live expected price + price check on the audit form
  const lineForm = $("[data-line-form]");
  const planEl = $("#plan-data");
  if (lineForm && planEl) {
    const plan = JSON.parse(planEl.textContent || "{}");
    const prog = $("[data-program]", lineForm), sku = $("[data-sku]", lineForm);
    const obs = $("[data-observed]", lineForm), out = $("[data-expected-out]", lineForm);
    const dtype = $("[data-dtype]", lineForm), fu = $("[data-followup]", lineForm);
    const money = (v) => "$" + Number(v).toFixed(2);
    let mismatch = false;
    function update() {
      const p = plan[prog.value];
      mismatch = false;
      if (!p) { out.textContent = ""; toggleFollow(); return; }
      const e = p[sku.value] || p["All"];
      let text = e.price == null ? "Plan price: not set (" + e.basis + ")" : "Plan price: " + money(e.price) + " (" + e.basis + ")";
      out.className = "expected span2";
      const o = parseFloat((obs.value || "").replace("$", ""));
      if (!isNaN(o) && e.price != null) {
        if (Math.abs(o - e.price) < 0.005) { text += " ✓ Match"; out.className += " ok-text"; }
        else { mismatch = true; text += o > e.price ? " ✗ Over plan" : " ✗ Under plan"; out.className += " bad-text"; }
      }
      out.textContent = text;
      toggleFollow();
    }
    function toggleFollow() {
      if (fu) fu.hidden = !(mismatch || (dtype && dtype.value !== "None"));
    }
    [prog, sku, dtype].forEach((el) => el && el.addEventListener("change", update));
    obs.addEventListener("input", update);
    update();
  }
})();
