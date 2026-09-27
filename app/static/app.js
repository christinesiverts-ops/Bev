// Chain Audit - progressive enhancement only; every page works without JS.
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const money = (v) => "$" + Number(v).toFixed(2);

  $$("[data-autosubmit]").forEach((el) => el.addEventListener("change", () => el.form && el.form.submit()));

  // confirmations, loading labels, double-submit guard
  $$("form").forEach((f) => {
    f.addEventListener("submit", (e) => {
      const msg = f.getAttribute("data-confirm");
      if (msg && !window.confirm(msg)) { e.preventDefault(); return; }
      if (f.method.toLowerCase() !== "post") return;
      const btn = e.submitter || $("button[data-loading]", f);
      setTimeout(() => {
        $$("button", f).forEach((b) => { b.disabled = true; });
        if (btn && btn.dataset.loading) {
          btn.innerHTML = '<svg class="size-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity=".25" stroke-width="3"/><path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>' + btn.dataset.loading;
        }
      }, 0);
    });
  });

  // toasts: dismiss + auto-hide
  $$("[data-toast]").forEach((t) => {
    const close = () => { t.style.opacity = "0"; setTimeout(() => t.remove(), 200); };
    const b = $("[data-dismiss]", t); if (b) b.addEventListener("click", close);
    setTimeout(close, t.classList.contains("toast-bad") ? 9000 : 5000);
  });

  // close menus on outside click
  document.addEventListener("click", (e) => {
    $$("details[data-menu][open]").forEach((d) => { if (!d.contains(e.target)) d.removeAttribute("open"); });
  });

  $$("[data-back]").forEach((a) => a.addEventListener("click", (e) => { if (history.length > 1) { e.preventDefault(); history.back(); } }));

  // GPS on check-in
  const checkin = $("#checkin-form");
  if (checkin) {
    const status = $("[data-gps-status]", checkin);
    const set = (text, cls) => { status.textContent = text; status.dataset.state = cls; };
    if (!("geolocation" in navigator)) {
      set("This browser can't share location. You can still check in.", "warn");
    } else {
      navigator.geolocation.getCurrentPosition((pos) => {
        checkin.lat.value = pos.coords.latitude.toFixed(6);
        checkin.lng.value = pos.coords.longitude.toFixed(6);
        checkin.accuracy.value = Math.round(pos.coords.accuracy);
        set("Location locked in (±" + Math.round(pos.coords.accuracy) + " m)", "ok");
      }, () => set("Location is off, so this visit will show \"No GPS\". You can still check in.", "warn"),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    }
  }

  $$("[data-fill-gps]").forEach((btn) => btn.addEventListener("click", () => {
    const f = btn.form;
    navigator.geolocation && navigator.geolocation.getCurrentPosition((pos) => {
      f.lat.value = pos.coords.latitude.toFixed(6); f.lng.value = pos.coords.longitude.toFixed(6);
    }, () => alert("Couldn't get your location."));
  }));

  // live price verdict for every check form
  const planEl = $("#plan-data");
  const plan = planEl ? JSON.parse(planEl.textContent || "{}") : {};
  $$("[data-line-form]").forEach((form) => {
    const progSel = $("[data-program-select]", form);
    const sku = $("[data-sku]", form), obs = $("[data-observed]", form);
    const out = $("[data-verdict]", form), dtype = $("[data-dtype]", form), fu = $("[data-followup]", form);
    let mismatch = false;
    const pid = () => (progSel ? progSel.value : form.dataset.program);
    function update() {
      mismatch = false;
      const p = plan[pid()];
      if (!p || !out) { toggle(); return; }
      const e = p[sku.value] || p["All"];
      const o = parseFloat((obs.value || "").replace("$", ""));
      let html = "";
      if (e.price == null) {
        html = '<span class="text-muted-foreground">No plan price for this SKU. Log what you see.</span>';
      } else if (isNaN(o)) {
        html = '<span class="text-muted-foreground">Plan: ' + money(e.price) + ' · ' + e.basis + '</span>';
      } else if (Math.abs(o - e.price) < 0.005) {
        html = '<span class="pill pill-success animate-pop">✓ Matches plan ' + money(e.price) + '</span>';
      } else {
        mismatch = true;
        const d = Math.abs(o - e.price);
        html = o > e.price
          ? '<span class="pill pill-danger animate-pop">✗ Over plan by ' + money(d) + '</span> <span class="text-muted-foreground">plan ' + money(e.price) + '</span>'
          : '<span class="pill pill-warning animate-pop">▲ Under plan by ' + money(d) + '</span> <span class="text-muted-foreground">plan ' + money(e.price) + '</span>';
      }
      out.innerHTML = html;
      toggle();
    }
    function toggle() {
      const bad = $$('input[value="N"]:checked, input[value="No"]:checked', form).length > 0;
      if (fu) fu.hidden = !(mismatch || bad || (dtype && dtype.value !== "None"));
    }
    [sku, dtype, progSel].forEach((el) => el && el.addEventListener("change", update));
    if (obs) obs.addEventListener("input", update);
    $$('input[type="radio"]', form).forEach((r) => r.addEventListener("change", toggle));
    update();
  });

  // recap: print + share the PDF (Web Share API with files; falls back to opening the PDF)
  $$("[data-print]").forEach((b) => b.addEventListener("click", () => window.print()));
  $$("[data-share-pdf]").forEach((b) => b.addEventListener("click", async () => {
    const url = b.dataset.sharePdf, title = b.dataset.shareTitle || "Recap";
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      const blob = await res.blob();
      const name = (res.headers.get("content-disposition") || "").split('filename="')[1];
      const file = new File([blob], name ? name.replace(/"$/, "") : "recap.pdf", { type: "application/pdf" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: title });
        return;
      }
    } catch (e) { if (e && e.name === "AbortError") return; }
    window.open(url, "_blank", "noopener");
  }));

  // invite link: copy + share
  $$("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    const src = $("[data-copy-source]");
    try { await navigator.clipboard.writeText(src.value); } catch (e) { src.select(); document.execCommand("copy"); }
    b.textContent = "Copied ✓"; setTimeout(() => { b.textContent = "Copy"; }, 2000);
  }));
  $$("[data-share-link]").forEach((b) => b.addEventListener("click", async () => {
    const url = b.dataset.shareLink, text = b.dataset.shareText || "";
    if (navigator.share) { try { await navigator.share({ title: document.title, text: text, url: url }); return; } catch (e) { if (e.name === "AbortError") return; } }
    try { await navigator.clipboard.writeText(url); b.textContent = "Link copied ✓"; } catch (e) { window.prompt("Copy this link", url); }
  }));

  // photo previews
  $$("[data-photos]").forEach((input) => {
    const strip = document.createElement("div");
    strip.className = "mt-2 flex flex-wrap gap-2";
    input.insertAdjacentElement("afterend", strip);
    input.addEventListener("change", () => {
      strip.innerHTML = "";
      Array.from(input.files || []).slice(0, 8).forEach((file) => {
        const url = URL.createObjectURL(file);
        const span = document.createElement("span");
        span.className = "thumb animate-pop";
        const img = document.createElement("img");
        img.src = url; img.alt = "Selected photo";
        span.appendChild(img); strip.appendChild(span);
      });
    });
  });
})();
