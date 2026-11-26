/* RiverScan: turns data/signals.json (written by scan.py every morning) into signal cards.
   Used by the homepage feed and the signal log page. */
(function () {
  var TAGS = {
    status: ["tag--status", "Status change"],
    primary_completion: ["tag--date", "Date slip"],
    completion: ["tag--date", "Date slip"],
    enrollment: ["tag--enrol", "Enrolment"],
    phase: ["tag--phase", "Phase change"],
    has_results: ["tag--phase", "Results posted"],
    status_override: ["tag--status", "Status change"],
    target_enrolment: ["tag--enrol", "Enrolment"],
    final_enrolment: ["tag--enrol", "Enrolment"],
    recruitment_start: ["tag--date", "Date change"],
    recruitment_end: ["tag--date", "Date slip"],
    overall_end: ["tag--date", "Date slip"],
    end_date: ["tag--date", "Date slip"],
    member_states: ["tag--phase", "Countries"],
    halts: ["tag--status", "Halted"],
    safety_measures: ["tag--status", "Safety measure"],
    serious_breaches: ["tag--status", "Serious breach"]
  };

  function esc(s) {
    return String(s == null ? "–" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function nice(v) {
    if (v == null || v === "") return "not set";
    var s = String(v);
    if (/^PHASE|EARLY_PHASE|^NA$/.test(s)) {
      return s.replace(/EARLY_PHASE1/g, "Early Phase 1").replace(/PHASE(\d)/g, "Phase $1")
              .replace(/\/Phase /g, "/").replace(/^NA$/, "N/A");
    }
    if (/^[A-Z_]+$/.test(s)) {
      s = s.toLowerCase().replace(/_/g, " ");
      s = s.charAt(0).toUpperCase() + s.slice(1);
      return s.replace("Active not recruiting", "Active, not recruiting");
    }
    return s;
  }
  function money(v, cur) {
    if (!v) return "value not stated";
    var sym = (!cur || cur === "GBP") ? "£" : cur + " ", units = [[1e9, "bn"], [1e6, "m"], [1e3, "k"]];
    for (var i = 0; i < units.length; i++) if (v >= units[i][0]) return sym + (v / units[i][0]).toFixed(1).replace(/\.0$/, "") + units[i][1];
    return sym + Math.round(v);
  }
  function tagFor(s) {
    if (s.type === "contract_award") return ["tag--contract", s.framework ? "Framework place" : "Contract award"];
    if (s.type === "mismatch") return ["tag--mismatch", "Registry mismatch"];
    if (s.type === "new_trial") return ["tag--enrol", "New trial"];
    if (s.type === "removed") return ["tag--status", "Delisted"];
    return TAGS[s.field] || ["tag--phase", "Change"];
  }
  function sentence(s) {
    var o = "<strong>" + esc(nice(s.old)) + "</strong>", n = "<strong>" + esc(nice(s.new)) + "</strong>";
    var title = s.title || s.trial || "";
    if (s.type === "contract_award") {
      var amt = "<strong>" + esc(money(s.new, s.currency)) + "</strong>";
      return (s.framework ? "Named on a " + amt + " framework: " : "Won a " + amt + " contract: ") + esc(title) + ".";
    }
    if (s.type === "mismatch") {
      var a = String(s.old || "").split(": "), b = String(s.new || "").split(": ");
      return esc(a[0]) + " says <strong>" + esc(nice(a[1])) + "</strong>, " + esc(b[0]) + " says <strong>" + esc(nice(b[1])) + "</strong>.";
    }
    if (s.type === "new_trial") return "New trial registered: " + esc(title) + ".";
    if (s.type === "removed") return "Trial no longer listed under this sponsor: " + esc(title) + ".";
    switch (s.field) {
      case "status":
        var why = (s.note || "").match(/reason given: (.*)\)$/);
        return "Trial status moved from " + o + " to " + n + "." + (why ? " Reason given: " + esc(why[1]) + "." : "");
      case "primary_completion": return "Primary completion date moved from " + o + " to " + n + ".";
      case "completion": return "Study completion date moved from " + o + " to " + n + ".";
      case "enrollment": return "Enrolment changed from " + o + " to " + n + " participants.";
      case "phase": return "Phase changed from " + o + " to " + n + ".";
      case "has_results": return "<strong>Results posted</strong> to the registry.";
      case "status_override": return "Trial status moved from " + o + " to " + n + ".";
      case "target_enrolment": case "final_enrolment": return esc(s.note) + ": " + o + " to " + n + " participants.";
      case "recruitment_start": case "recruitment_end": case "overall_end": case "end_date":
        return esc((s.note || "Date changed").replace(" changed", "")) + " moved from " + o + " to " + n + ".";
      case "member_states": return "Countries authorised changed from " + o + " to " + n + ".";
      case "halts": return "<strong>Temporary halt</strong> recorded on the EU register.";
      case "safety_measures": return "<strong>Urgent safety measure</strong> recorded on the EU register.";
      case "serious_breaches": return "<strong>Serious breach</strong> recorded on the EU register.";
    }
    return esc(s.note);
  }
  // Long titles start collapsed to three lines with a button to read the rest.
  function text(s) {
    var body = sentence(s).replace(/\.\.$/, ".");
    if ((s.title || s.trial || "").length <= 150) return "<p>" + body + "</p>";
    return '<p class="signal-text is-clamped">' + body + "</p>" +
      '<button type="button" class="signal-more" aria-expanded="false">Show more</button>';
  }
  if (typeof document !== "undefined") {
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".signal-more");
      if (!b) return;
      var p = b.previousElementSibling, open = b.getAttribute("aria-expanded") === "true";
      p.classList.toggle("is-clamped", open);
      b.setAttribute("aria-expanded", open ? "false" : "true");
      b.textContent = open ? "Show more" : "Show less";
    });
  }

  function when(ts) {
    var d = new Date(ts);
    return isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  window.RiverScan = {
    card: function (s, opts) {
      var t = tagFor(s), ref = s.ref || s.nct_id, title = s.title || s.trial;
      var source = s.source || "ClinicalTrials.gov";
      var sub = "";
      if (s.type === "contract_award") sub = '<p class="signal-trial">Buyer: ' + esc(s.buyer) + (s.published ? " · published " + esc(when(s.published)) : "") + "</p>";
      else if (s.type === "change" || s.type === "mismatch") sub = '<p class="signal-trial">' + esc(title) + "</p>";
      var links = '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.type === "mismatch" ? String(ref).split(" / ")[0] : ref) + " ↗</a>";
      if (s.url2) links += '<a href="' + esc(s.url2) + '" target="_blank" rel="noopener">' + esc(String(ref).split(" / ")[1] || "Other record") + " ↗</a>";
      return '<article class="signal signal--' + esc(s.severity) + '">' +
        '<div class="signal-top"><span class="ticker">' + esc(s.ticker) + "</span>" +
        '<span class="tag ' + t[0] + '">' + t[1] + "</span>" +
        '<span class="signal-source">' + esc(source) + "</span></div>" +
        text(s) + sub +
        '<div class="signal-foot"><span class="sev sev--' + esc(s.severity) + '">' + esc(s.severity) + "</span>" + links +
        '<span class="signal-co">' + esc(s.company) + (opts && opts.short ? "" : " · " + esc(when(s.detected_at))) + "</span></div>" +
        "</article>";
    },
    load: function () {
      return fetch("data/signals.json", { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; })
        .then(function (d) {
          if (!Array.isArray(d)) return [];
          var rank = { high: 0, medium: 1, low: 2 };
          return d.slice().sort(function (a, b) {
            if (a.detected_at !== b.detected_at) return a.detected_at < b.detected_at ? 1 : -1;
            return (a.severity in rank ? rank[a.severity] : 3) - (b.severity in rank ? rank[b.severity] : 3);
          });
        });
    },
    when: when,
    money: money,
    stream: function (s) { return s.stream || "trials"; }
  };
})();
