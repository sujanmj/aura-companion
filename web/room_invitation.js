(function () {
  "use strict";

  var TOKEN_KEY = "AURA_SENSOR_API_TOKEN";
  var status = document.getElementById("room-invitation-status");
  var details = document.getElementById("room-invitation-details");
  var inviteNode = document.getElementById("room-invite-node");
  var transferNode = document.getElementById("room-transfer-node");
  var revokeNode = document.getElementById("room-revoke-node");
  var inviteButton = document.getElementById("room-invite-btn");
  var transferButton = document.getElementById("room-transfer-btn");
  var revokeButton = document.getElementById("room-revoke-btn");
  var refreshButton = document.getElementById("room-refresh-btn");
  var stopButton = document.getElementById("room-stop-btn");
  var currentSession = null;
  var busy = false;
  var needsRefresh = false;

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function errorMessage(error) {
    if (error && (error.message === "Failed to fetch" || error.name === "TypeError")) {
      return "Hub response unavailable. Refresh invitation status before retrying.";
    }
    return error && error.message || "Hub response unavailable. Refresh invitation status before retrying.";
  }

  function setBusy(value) {
    busy = value;
    refreshButton.disabled = value;
    inviteNode.disabled = value || inviteNode.options.length <= 1;
    transferNode.disabled = value || transferNode.options.length <= 1 || !currentSession;
    revokeNode.disabled = value || revokeNode.options.length <= 1;
    inviteButton.disabled = value || needsRefresh || inviteNode.disabled || !inviteNode.value;
    transferButton.disabled = value || needsRefresh || transferNode.disabled || !transferNode.value || !currentSession;
    revokeButton.disabled = value || needsRefresh || revokeNode.disabled || !revokeNode.value;
    stopButton.disabled = value || needsRefresh || !currentSession;
  }

  function clearSelect(select, placeholder) {
    select.replaceChildren();
    var option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    select.appendChild(option);
  }

  function validNode(node) {
    return node && typeof node.node_id === "string" &&
      /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(node.node_id) &&
      typeof node.display_name === "string" && typeof node.room === "string" &&
      node.disabled !== 1 && node.disabled !== true;
  }

  function renderNodes(nodes) {
    [inviteNode, transferNode, revokeNode].forEach(function (select) {
      clearSelect(select, "Select an enrolled room");
      nodes.filter(validNode).forEach(function (node) {
        var option = document.createElement("option");
        option.value = node.node_id;
        option.textContent = node.display_name + " · " + node.room + " · last seen " +
          (node.last_seen_at || "never");
        select.appendChild(option);
      });
    });
  }

  function validSession(session) {
    return session && typeof session.session_id === "string" &&
      /^[A-Fa-f0-9-]{1,64}$/.test(session.session_id) &&
      typeof session.node_id === "string" &&
      /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(session.node_id) &&
      Number.isInteger(session.generation) && session.generation > 0 &&
      typeof session.expires_at === "number" && Number.isFinite(session.expires_at);
  }

  function renderSession(session) {
    currentSession = validSession(session) ? session : null;
    if (currentSession) {
      details.textContent = "Room: " + currentSession.node_id + " · Session: " +
        currentSession.session_id + " · Generation: " + currentSession.generation +
        " · Expires: " + new Date(currentSession.expires_at * 1000).toLocaleString();
    } else {
      details.textContent = "No active room invitation.";
    }
    setBusy(busy);
  }

  function makeRequest(path, method, payload) {
    var apiToken = token();
    if (apiToken.length < 32 || apiToken.trim() !== apiToken) {
      return Promise.reject(new Error("Enter the hub administrator token above."));
    }
    var headers = { Accept: "application/json", "X-AURA-API-Token": apiToken };
    var options = { method: method, headers: headers, redirect: "error" };
    if (payload !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    return fetch(path, options).then(function (response) {
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error("Access denied. Check the hub administrator token.");
        }
        if (response.status === 409) {
          throw new Error("The invitation changed or that room is unavailable. Refresh status and check its last heartbeat.");
        }
        throw new Error("The hub rejected the request (HTTP " + response.status + ").");
      }
      return response.json().then(function (body) {
        if (!body || body.ok !== true) {
          throw new Error("The hub returned an invalid response.");
        }
        return body;
      });
    });
  }

  function refresh() {
    if (!token()) {
      currentSession = null;
      details.textContent = "";
      renderNodes([]);
      setStatus("Connect with the API token above to manage room invitations.");
      setBusy(false);
      return Promise.resolve();
    }
    setBusy(true);
    setStatus("Refreshing invitation status…");
    return Promise.all([
      makeRequest("/rooms/status", "POST", {}),
      makeRequest("/nodes/status", "GET"),
    ]).then(function (results) {
      var session = results[0].session;
      if (session !== null && !validSession(session)) {
        throw new Error("The hub returned invalid invitation data.");
      }
      renderSession(session);
      renderNodes(Array.isArray(results[1].nodes) ? results[1].nodes : []);
      needsRefresh = false;
      setStatus(currentSession ? "One room is invited. No sensor or audio action is active." : "No active room invitation.");
      setBusy(false);
    }).catch(function (error) {
      currentSession = null;
      needsRefresh = true;
      details.textContent = "";
      renderNodes([]);
      setStatus(errorMessage(error));
      setBusy(false);
    });
  }

  function confirmPhrase(expected, explanation) {
    return window.prompt(explanation + " Type exactly: " + expected) === expected;
  }

  function mutate(action, payload, expected, explanation) {
    if (needsRefresh) return;
    if (!confirmPhrase(expected, explanation)) {
      setStatus("Canceled. No room change was sent.");
      return;
    }
    setBusy(true);
    setStatus("Sending one invitation request…");
    makeRequest("/rooms/" + action, "POST", payload).then(function () {
      setStatus("Invitation updated.");
      return refresh();
    }).catch(function (error) {
      needsRefresh = true;
      setStatus(errorMessage(error));
      setBusy(false);
    });
  }

  inviteNode.addEventListener("change", function () { setBusy(busy); });
  transferNode.addEventListener("change", function () { setBusy(busy); });
  revokeNode.addEventListener("change", function () { setBusy(busy); });
  inviteButton.addEventListener("click", function () {
    var nodeId = inviteNode.value;
    if (!nodeId || busy || needsRefresh) return;
    mutate("start", { node_id: nodeId, approved: true }, "INVITE " + nodeId,
      "This reserves one reply in the selected room for up to five minutes.");
  });
  transferButton.addEventListener("click", function () {
    var nodeId = transferNode.value;
    if (!nodeId || !currentSession || busy || needsRefresh) return;
    mutate("transfer", {
      session_id: currentSession.session_id,
      generation: currentSession.generation,
      node_id: nodeId,
      approved: true,
    }, "TRANSFER " + nodeId, "This moves the current invitation to the selected room.");
  });
  revokeButton.addEventListener("click", function () {
    var nodeId = revokeNode.value;
    if (!nodeId || busy || needsRefresh) return;
    if (!confirmPhrase("REVOKE " + nodeId,
      "This immediately disables this node credential and ends its active invitation. It does not power off the device.")) {
      setStatus("Canceled. No node credential was revoked.");
      return;
    }
    setBusy(true);
    setStatus("Revoking the selected node credential…");
    makeRequest("/nodes/revoke", "POST", { node_id: nodeId }).then(function (body) {
      if (body.revoked !== true) throw new Error("The hub did not confirm node revocation.");
      return refresh().then(function () {
        if (!needsRefresh) {
          setStatus("Node credential revoked. The device itself was not powered off.");
        }
      });
    }).catch(function (error) {
      needsRefresh = true;
      setStatus(errorMessage(error));
      setBusy(false);
    });
  });
  stopButton.addEventListener("click", function () {
    if (!currentSession || busy || needsRefresh) return;
    var session = currentSession;
    mutate("stop", {
      session_id: session.session_id,
      generation: session.generation,
    }, "STOP " + session.session_id, "This ends the current room invitation now.");
  });
  refreshButton.addEventListener("click", refresh);
  window.addEventListener("aura-token-changed", refresh);
  refresh();
})();
