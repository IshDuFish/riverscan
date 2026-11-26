/* RiverScan: turns data/signals.json (written by scan.py every morning) into signal cards.
   Used by the homepage feed and the signal log page. */
(function () {
  var TAGS = {
    status: ["tag--status", "Status change"],
    primary_completion: ["tag--date", "Date slip"],
    completion: ["tag--date", "Date slip"],
    enrollment: ["tag--enrol", "Enrolment"],
    phase: ["tag--phase", "Phase change"],
    has_results: ["tag--phase", "Results posted"]
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
  function tagFor(s) {
    if (s.type === "new_trial") return ["tag--enrol", "New trial"];
    if (s.type === "removed") return ["tag--status", "Delisted"];
    return TAGS[s.field] || ["tag--phase", "Change"];
  }
  function sentence(s) {
    var o = "<strong>" + esc(nice(s.old)) + "</strong>", n = "<strong>" + esc(nice(s.new)) + "</strong>";
    if (s.type === "new_trial") return "New trial registered: " + esc(s.trial) + ".";
    if (s.type === "removed") return "Trial no longer listed under this sponsor: " + esc(s.trial) + ".";
    switch (s.field) {
      case "status":
        var why = (s.note || "").match(/reason given: (.*)\)$/);
        return "Trial status moved from " + o + " to " + n + "." + (why ? " Reason given: " + esc(why[1]) + "." : "");
      case "primary_completion": return "Primary completion date moved from " + o + " to " + n + ".";
      case "completion": return "Study completion date moved from " + o + " to " + n + ".";
      case "enrollment": return "Enrolment changed from " + o + " to " + n + " participants.";
      case "phase": return "Phase changed from " + o + " to " + n + ".";
      case "has_results": return "<strong>Results posted</strong> to the registry.";
    }
    return esc(s.note);
  }
  function when(ts) {
    var d = new Date(ts);
    return isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  window.RiverScan = {
    card: function (s, opts) {
      var t = tagFor(s);
      var titleLine = (s.type === "change")
        ? '<p class="signal-trial">' + esc(s.trial) + "</p>" : "";
      return '<article class="signal signal--' + esc(s.severity) + '">' +
        '<div class="signal-top"><span class="ticker">' + esc(s.ticker) + "</span>" +
        '<span class="tag ' + t[0] + '">' + t[1] + "</span>" +
        '<span class="signal-source">' + (opts && opts.short ? "ClinicalTrials.gov" : when(s.detected_at)) + "</span></div>" +
        "<p>" + sentence(s) + "</p>" + titleLine +
        '<div class="signal-foot"><span class="sev sev--' + esc(s.severity) + '">' + esc(s.severity) + "</span>" +
        '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.nct_id) + " ↗</a>" +
        (opts && opts.short ? "" : '<span class="signal-co">' + esc(s.company) + "</span>") + "</div>" +
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
    when: when
  };
})();
