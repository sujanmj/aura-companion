(function () {
  "use strict";

  var TOKEN_KEY = "AURA_SENSOR_API_TOKEN";
  var REFRESH_MS = 5000;

  var tokenInput = document.getElementById("token-input");
  var saveTokenBtn = document.getElementById("save-token-btn");
  var clearTokenBtn = document.getElementById("clear-token-btn");
  var tokenMessage = document.getElementById("token-message");
  var statusBadge = document.getElementById("status-badge");
  var lastRefreshed = document.getElementById("last-refreshed");

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setTokenMessage(text) {
    tokenMessage.textContent = text || "";
  }

  function setBadge(text, className) {
    statusBadge.textContent = text;
    statusBadge.className = "badge " + className;
  }

  function loadTokenIntoField() {
    tokenInput.value = getToken();
  }

  function saveToken() {
    var value = tokenInput.value.trim();
    if (!value) {
      setTokenMessage("Enter a token before saving.");
      return;
    }
    localStorage.setItem(TOKEN_KEY, value);
    setTokenMessage("Token saved in this browser.");
    refreshDashboard();
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    tokenInput.value = "";
    setTokenMessage("Token cleared.");
    refreshDashboard();
  }

  function severityClass(value) {
    var key = (value || "unknown").toLowerCase();
    if (key === "critical" || key === "high" || key === "medium" || key === "low") {
      return "severity-" + key;
    }
    return "severity-low";
  }

  function statusClass(value) {
    var key = (value || "none").toLowerCase();
    if (key === "dispatched" || key === "ignored") {
      return "status-" + key;
    }
    return "status-none";
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTable(container, columns, rows, emptyText) {
    if (!rows || rows.length === 0) {
      container.innerHTML = '<p class="empty-state">' + escapeHtml(emptyText) + "</p>";
      return;
    }

    var html = ["<table><thead><tr>"];
    columns.forEach(function (col) {
      html.push("<th>" + escapeHtml(col.label) + "</th>");
    });
    html.push("</tr></thead><tbody>");

    rows.forEach(function (row) {
      html.push("<tr>");
      columns.forEach(function (col) {
        var raw = col.value(row);
        var cell = col.render ? col.render(raw, row) : escapeHtml(raw);
        html.push("<td>" + cell + "</td>");
      });
      html.push("</tr>");
    });

    html.push("</tbody></table>");
    container.innerHTML = html.join("");
  }

  function renderSummary(summary) {
    document.getElementById("metric-recent-events").textContent = summary.recent_event_count ?? "0";
    document.getElementById("metric-pending-events").textContent = summary.pending_event_count ?? "0";
    document.getElementById("metric-actions").textContent = summary.recent_action_count ?? "0";
    document.getElementById("metric-rooms").textContent = summary.rooms_active_count ?? "0";
    document.getElementById("metric-critical").textContent = summary.critical_or_high_event_count ?? "0";
  }

  function renderDashboard(data) {
    renderSummary(data.summary || {});

    renderTable(
      document.getElementById("critical-alerts"),
      [
        { label: "ID", value: function (r) { return r.event_id; } },
        { label: "Type", value: function (r) { return r.event_type; } },
        { label: "Room", value: function (r) { return r.room; } },
        {
          label: "Severity",
          value: function (r) { return r.severity; },
          render: function (value) {
            return '<span class="' + severityClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        {
          label: "Status",
          value: function (r) { return r.action_status; },
          render: function (value) {
            return '<span class="' + statusClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        { label: "Summary", value: function (r) { return r.summary; } },
      ],
      data.critical_alerts || [],
      "No critical or high alerts."
    );

    renderTable(
      document.getElementById("active-rooms"),
      [
        { label: "Room", value: function (r) { return r.room; } },
        { label: "Events", value: function (r) { return r.event_count; } },
        {
          label: "Severity",
          value: function (r) { return r.highest_severity; },
          render: function (value) {
            return '<span class="' + severityClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        { label: "Pending", value: function (r) { return r.pending_count; } },
        { label: "Dispatched", value: function (r) { return r.dispatched_count; } },
        { label: "Last Event", value: function (r) { return r.last_event_at || "—"; } },
      ],
      data.rooms || [],
      "No active rooms."
    );

    renderTable(
      document.getElementById("recent-events"),
      [
        { label: "ID", value: function (r) { return r.id; } },
        { label: "Type", value: function (r) { return r.event_type; } },
        { label: "Room", value: function (r) { return r.room || "unknown"; } },
        {
          label: "Severity",
          value: function (r) { return r.severity; },
          render: function (value) {
            return '<span class="' + severityClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        {
          label: "Status",
          value: function (r) { return r.action_status || "none"; },
          render: function (value) {
            return '<span class="' + statusClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        { label: "Summary", value: function (r) { return r.event_summary; } },
      ],
      data.latest_events || [],
      "No recent events."
    );

    renderTable(
      document.getElementById("recent-actions"),
      [
        { label: "ID", value: function (r) { return r.id; } },
        { label: "Type", value: function (r) { return r.action_type; } },
        { label: "Status", value: function (r) { return r.status; } },
        { label: "Target", value: function (r) { return r.target || "—"; } },
        { label: "Summary", value: function (r) { return r.action_summary; } },
      ],
      data.recent_actions || [],
      "No recent actions."
    );
  }

  function refreshDashboard() {
    var headers = { Accept: "application/json" };
    var token = getToken();
    if (token) {
      headers["X-AURA-API-Token"] = token;
    }

    fetch("/dashboard/status", { headers: headers })
      .then(function (response) {
        if (response.status === 401) {
          setBadge("Locked", "badge-locked");
          setTokenMessage("Dashboard locked. Paste your AURA sensor API token.");
          throw new Error("unauthorized");
        }
        if (!response.ok) {
          throw new Error("http-" + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (!data.ok) {
          throw new Error("bad-response");
        }
        renderDashboard(data);
        setBadge("Live", "badge-ok");
        setTokenMessage(token ? "Dashboard connected." : "No token configured. API may be open on local host.");
        lastRefreshed.textContent = "Last refreshed: " + new Date().toLocaleTimeString();
      })
      .catch(function (error) {
        if (error && error.message === "unauthorized") {
          return;
        }
        setBadge("Offline", "badge-error");
        if (error && error.message && error.message.indexOf("Failed to fetch") !== -1) {
          setTokenMessage("Cannot reach AURA API. Start python scripts/run_sensor_api.py");
        } else {
          setTokenMessage("Dashboard refresh failed. Check API server and token.");
        }
      });
  }

  saveTokenBtn.addEventListener("click", saveToken);
  clearTokenBtn.addEventListener("click", clearToken);

  loadTokenIntoField();
  refreshDashboard();
  setInterval(refreshDashboard, REFRESH_MS);
})();
