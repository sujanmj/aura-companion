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
  var timelinePanel = document.getElementById("timeline-panel");
  var timelineTitle = document.getElementById("timeline-title");
  var closeTimelineBtn = document.getElementById("close-timeline-btn");

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

  function confirmationStatusClass(value) {
    var key = (value || "pending").toLowerCase();
    if (
      key === "pending" ||
      key === "confirmed_ok" ||
      key === "confirmed_escalate" ||
      key === "cancelled" ||
      key === "expired"
    ) {
      return "confirmation-status confirmation-status-" + key;
    }
    return "confirmation-status confirmation-status-pending";
  }

  function incidentStatusClass(value) {
    var key = (value || "open").toLowerCase();
    if (
      key === "open" ||
      key === "resolved" ||
      key === "expired" ||
      key === "cancelled" ||
      key === "simulated_escalated"
    ) {
      return "confirmation-status incident-status-" + key;
    }
    return "confirmation-status incident-status-open";
  }

  function runtimeStatusClass(value) {
    var key = (value || "missing").toLowerCase();
    if (
      key === "online" ||
      key === "stale" ||
      key === "missing" ||
      key === "offline" ||
      key === "enabled" ||
      key === "disabled"
    ) {
      return "confirmation-status runtime-status-" + key;
    }
    return "confirmation-status runtime-status-missing";
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
    document.getElementById("metric-pending-confirmations").textContent =
      summary.pending_confirmation_count ?? "0";
  }

  function respondToConfirmation(confirmationId, response) {
    var headers = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
    var token = getToken();
    if (token) {
      headers["X-AURA-API-Token"] = token;
    }

    fetch("/confirmations/respond", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({
        confirmation_id: confirmationId,
        response: response,
      }),
    })
      .then(function (res) {
        if (!res.ok) {
          throw new Error("respond-failed");
        }
        return res.json();
      })
      .then(function (body) {
        if (!body.ok) {
          throw new Error("respond-bad-response");
        }
        refreshDashboard();
      })
      .catch(function () {
        setTokenMessage("Failed to submit confirmation response.");
      });
  }

  function renderPendingConfirmations(confirmations) {
    var container = document.getElementById("pending-confirmations");
    if (!confirmations || confirmations.length === 0) {
      container.innerHTML = '<p class="empty-state">No pending confirmations.</p>';
      return;
    }

    var html = [];
    confirmations.forEach(function (item) {
      var id = item.id;
      var eventType = item.confirmation_type || "safety";
      if (item.metadata && item.metadata.event_type) {
        eventType = item.metadata.event_type;
      }
      html.push('<article class="confirmation-card" data-id="' + escapeHtml(id) + '">');
      html.push('<div class="confirmation-card-header">');
      html.push("<div><strong>#" + escapeHtml(id) + "</strong> · " + escapeHtml(eventType) + "</div>");
      html.push('<span class="' + confirmationStatusClass(item.status) + '">' + escapeHtml(item.status || "pending") + "</span>");
      html.push("</div>");
      html.push(
        '<div class="confirmation-meta">Created: ' +
          escapeHtml(item.created_at || "—") +
          "</div>"
      );
      html.push('<p class="confirmation-prompt">' + escapeHtml(item.prompt || "") + "</p>");
      html.push('<div class="confirmation-actions">');
      html.push(
        '<button type="button" class="btn-confirm-ok" data-action="ok" data-id="' +
          escapeHtml(id) +
          '">I\'m okay</button>'
      );
      html.push(
        '<button type="button" class="btn-confirm-notify" data-action="notify" data-id="' +
          escapeHtml(id) +
          '">Notify simulated contact</button>'
      );
      html.push(
        '<button type="button" class="btn-confirm-cancel" data-action="cancel" data-id="' +
          escapeHtml(id) +
          '">Cancel</button>'
      );
      html.push("</div></article>");
    });
    container.innerHTML = html.join("");

    container.querySelectorAll("button[data-action]").forEach(function (button) {
      button.addEventListener("click", function () {
        var confirmationId = parseInt(button.getAttribute("data-id"), 10);
        var action = button.getAttribute("data-action");
        if (!confirmationId || !action) {
          return;
        }
        respondToConfirmation(confirmationId, action);
      });
    });
  }

  function renderIncidentList(containerId, incidents, emptyText) {
    var container = document.getElementById(containerId);
    if (!incidents || incidents.length === 0) {
      container.innerHTML = '<p class="empty-state">' + escapeHtml(emptyText) + "</p>";
      return;
    }

    var html = [];
    incidents.forEach(function (item) {
      html.push('<article class="incident-card" data-id="' + escapeHtml(item.id) + '">');
      html.push('<div class="incident-card-header">');
      html.push(
        "<div><strong>#" +
          escapeHtml(item.id) +
          "</strong> · " +
          escapeHtml(item.title || item.incident_type || "incident") +
          "</div>"
      );
      html.push(
        '<span class="' +
          incidentStatusClass(item.status) +
          '">' +
          escapeHtml(item.status || "open") +
          "</span>"
      );
      html.push("</div>");
      html.push(
        '<div class="incident-meta">Room: ' +
          escapeHtml(item.room || "unknown") +
          " · Severity: " +
          escapeHtml(item.severity || "unknown") +
          " · Started: " +
          escapeHtml(item.started_at || "—") +
          "</div>"
      );
      html.push('<p class="incident-summary">' + escapeHtml(item.summary || "") + "</p>");
      html.push('<div class="incident-actions">');
      html.push(
        '<button type="button" class="btn-view-timeline" data-id="' +
          escapeHtml(item.id) +
          '">View Timeline</button>'
      );
      html.push("</div></article>");
    });
    container.innerHTML = html.join("");

    container.querySelectorAll(".btn-view-timeline").forEach(function (button) {
      button.addEventListener("click", function () {
        var incidentId = parseInt(button.getAttribute("data-id"), 10);
        if (incidentId) {
          loadIncidentTimeline(incidentId);
        }
      });
    });
  }

  function renderTimelineItems(timeline) {
    var container = document.getElementById("incident-timeline");
    if (!timeline || timeline.length === 0) {
      container.innerHTML = '<p class="empty-state">No timeline items.</p>';
      return;
    }

    var html = [];
    timeline.forEach(function (item) {
      html.push('<article class="timeline-item">');
      html.push(
        '<div class="timeline-item-type">' +
          escapeHtml(item.created_at || "—") +
          " · " +
          escapeHtml(item.item_type || "item") +
          "</div>"
      );
      html.push('<div class="timeline-item-title">' + escapeHtml(item.title || "") + "</div>");
      if (item.status) {
        html.push(
          '<div class="incident-meta">Status: ' + escapeHtml(item.status) + "</div>"
        );
      }
      if (item.summary) {
        html.push(
          '<div class="timeline-item-summary">' + escapeHtml(item.summary) + "</div>"
        );
      }
      html.push("</article>");
    });
    container.innerHTML = html.join("");
  }

  function loadIncidentTimeline(incidentId) {
    var headers = { Accept: "application/json" };
    var token = getToken();
    if (token) {
      headers["X-AURA-API-Token"] = token;
    }

    fetch("/incidents/" + incidentId, { headers: headers })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("timeline-fetch-failed");
        }
        return response.json();
      })
      .then(function (data) {
        if (!data.ok) {
          throw new Error("timeline-bad-response");
        }
        timelineTitle.textContent =
          "Incident #" + incidentId + ": " + (data.incident && data.incident.title ? data.incident.title : "");
        renderTimelineItems(data.timeline || []);
        timelinePanel.classList.remove("hidden");
        timelinePanel.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(function () {
        setTokenMessage("Failed to load incident timeline.");
      });
  }

  function renderRuntimeHealth(runtimeHealth) {
    var container = document.getElementById("runtime-health");
    var services = (runtimeHealth && runtimeHealth.services) || [];
    if (services.length === 0) {
      container.innerHTML = '<p class="empty-state">No runtime health data.</p>';
      return;
    }

    var html = [];
    services.forEach(function (service) {
      var name = service.service_name || "unknown";
      var status = service.effective_status || service.status || "missing";
      html.push('<article class="runtime-health-card">');
      html.push('<h3>' + escapeHtml(name) + "</h3>");
      html.push(
        '<div><span class="' +
          runtimeStatusClass(status) +
          '">' +
          escapeHtml(status) +
          "</span></div>"
      );
      html.push('<div class="runtime-health-meta">');
      if (service.age_seconds !== null && service.age_seconds !== undefined) {
        html.push("Age: " + escapeHtml(service.age_seconds) + "s<br>");
      }
      if (service.pid) {
        html.push("PID: " + escapeHtml(service.pid) + "<br>");
      }
      if (service.last_seen_at) {
        html.push("Last seen: " + escapeHtml(service.last_seen_at));
      }
      html.push("</div></article>");
    });
    container.innerHTML = html.join("");
  }

  function renderDashboard(data) {
    renderSummary(data.summary || {});
    renderRuntimeHealth(data.runtime_health || {});
    renderPendingConfirmations(data.pending_confirmations || []);
    renderIncidentList("open-incidents", data.open_incidents || [], "No open incidents.");
    renderIncidentList("recent-incidents", data.recent_incidents || [], "No recent incidents.");

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
      document.getElementById("recent-confirmations"),
      [
        { label: "ID", value: function (r) { return r.id; } },
        { label: "Type", value: function (r) { return r.confirmation_type; } },
        {
          label: "Status",
          value: function (r) { return r.status; },
          render: function (value) {
            return '<span class="' + confirmationStatusClass(value) + '">' + escapeHtml(value) + "</span>";
          },
        },
        { label: "Response", value: function (r) { return r.response_text || "—"; } },
        { label: "Created", value: function (r) { return r.created_at || "—"; } },
        { label: "Responded", value: function (r) { return r.responded_at || "—"; } },
      ],
      data.recent_confirmations || [],
      "No recent confirmations."
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
  closeTimelineBtn.addEventListener("click", function () {
    timelinePanel.classList.add("hidden");
  });

  loadTokenIntoField();
  refreshDashboard();
  setInterval(refreshDashboard, REFRESH_MS);
})();
