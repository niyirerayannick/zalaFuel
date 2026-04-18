(function () {
    var root = document.documentElement;
    var body = document.body;
    var content = document.getElementById("driver-content");
    var loading = document.getElementById("driver-loading");
    var installPromptEvent = null;
    var currentTab = body.dataset.initialTab || "dashboard";
    var isSpa = body.dataset.driverSpa === "1";
    var assignmentStateUrl = body.dataset.assignmentStateUrl || "";
    var previousAssignmentState = null;
    var toastTimer = null;
    var notificationPanelOpen = false;
    var liveUpdatesPausedUntil = 0;
    var partialUrls = {
        dashboard: body.dataset.urlDashboard || "",
        trips: body.dataset.urlTrips || "",
        fuel: body.dataset.urlFuel || "",
        messages: body.dataset.urlMessages || "",
        profile: body.dataset.urlProfile || ""
    };
    var messageThreadUrl = body.dataset.urlMessagesThread || "";

    function updateTitle() {
        var title = document.getElementById("driver-page-title");
        if (!title) return;
        var titles = {
            dashboard: "Dashboard",
            trips: "Trips",
            fuel: "Fuel",
            messages: "Support",
            profile: "Profile"
        };
        title.textContent = titles[currentTab] || "Dashboard";
    }

    function updateNotificationBadge(count) {
        var badge = document.getElementById("notification-badge");
        if (!badge) return;
        badge.classList.toggle("hidden", Number(count || 0) <= 0);
    }

    function closePanels() {
        var notificationPanel = document.getElementById("driver-notification-panel");
        var profileMenu = document.getElementById("driver-profile-menu");
        if (notificationPanel) notificationPanel.classList.add("hidden");
        if (profileMenu) profileMenu.classList.add("hidden");
        notificationPanelOpen = false;
    }

    function renderNotificationPanel(state) {
        var countNode = document.getElementById("notification-panel-count");
        var listNode = document.getElementById("notification-panel-list");
        if (!countNode || !listNode) return;

        var notifications = (state && state.notifications) || [];
        countNode.textContent = String(Number(state && state.notification_count || 0));

        if (!notifications.length) {
            listNode.innerHTML = '<div class="rounded-2xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">No notifications yet.</div>';
            return;
        }

        listNode.innerHTML = notifications.map(function (item) {
            var icon = "notifications";
            if (item.kind === "trip") icon = "local_shipping";
            if (item.kind === "message") icon = "chat";
            if (item.kind === "fuel") icon = "local_gas_station";
            return (
                '<a href="' + (item.href || "#") + '" data-driver-notification-link="1" data-driver-tab="' + (item.kind === "message" ? "messages" : item.kind === "fuel" ? "fuel" : "trips") + '" class="flex items-start gap-3 rounded-2xl px-3 py-3 text-left transition hover:bg-green-50">' +
                    '<div class="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-green-50 text-green-700">' +
                        '<span class="material-symbols-outlined text-[18px]">' + icon + '</span>' +
                    '</div>' +
                    '<div class="min-w-0 flex-1">' +
                        '<p class="text-sm font-semibold text-slate-900">' + (item.title || "Update") + '</p>' +
                        '<p class="mt-1 text-sm text-slate-500">' + (item.body || "") + '</p>' +
                    '</div>' +
                '</a>'
            );
        }).join("");
    }

    function setActiveDriverTab(tabName) {
        var tabs = document.querySelectorAll(".driver-tab");
        tabs.forEach(function (tab) {
            var isActive = tab.dataset.tab === tabName;
            tab.classList.toggle("bg-green-50", isActive);
            tab.classList.toggle("text-green-700", isActive);
            tab.classList.toggle("shadow-sm", isActive);
            tab.classList.toggle("text-gray-500", !isActive);
        });
        updateTitle();
    }

    function showToast(message, href) {
        var toast = document.getElementById("driver-toast");
        if (!toast || !message) return;
        if (toastTimer) clearTimeout(toastTimer);
        toast.classList.remove("hidden");
        toast.innerHTML = "";

        var row = document.createElement("div");
        row.className = "flex items-center justify-between gap-3";

        var label = document.createElement("span");
        label.textContent = message;
        row.appendChild(label);

        if (href) {
            var link = document.createElement("a");
            link.href = href;
            link.className = "shrink-0 font-semibold underline";
            link.textContent = "Open";
            row.appendChild(link);
        }

        toast.appendChild(row);
        toastTimer = setTimeout(function () {
            toast.classList.add("hidden");
        }, 4000);
    }

    function setLoading(isLoading) {
        if (!loading) return;
        loading.classList.toggle("hidden", !isLoading);
        loading.classList.toggle("flex", isLoading);
    }

    function hasActiveFormFocus() {
        if (Date.now() < liveUpdatesPausedUntil) return true;
        var active = document.activeElement;
        if (!active) return false;
        if (active.matches("input, textarea, select")) return true;
        return Boolean(active.closest("form"));
    }

    function pauseLiveUpdates(ms) {
        liveUpdatesPausedUntil = Math.max(liveUpdatesPausedUntil, Date.now() + (ms || 15000));
    }

    function refreshDashboardStats() {
        if (!isSpa || currentTab !== "dashboard" || document.hidden || hasActiveFormFocus()) return;
        fetch(partialUrls.dashboard, { credentials: "same-origin" })
            .then(function (r) {
                if (!r.ok) throw new Error("dashboard refresh failed");
                return r.text();
            })
            .then(function (html) {
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, "text/html");
                var incoming = doc.querySelector("#driver-dashboard-stats");
                var current = document.querySelector("#driver-dashboard-stats");
                if (incoming && current) {
                    current.innerHTML = incoming.innerHTML;
                }
            })
            .catch(function () {});
    }

    function setupPwaInstall() {
        var installBtn = document.getElementById("install-app");
        if (!installBtn) return;

        window.addEventListener("beforeinstallprompt", function (event) {
            event.preventDefault();
            installPromptEvent = event;
            installBtn.classList.remove("hidden");
        });

        installBtn.addEventListener("click", function () {
            if (!installPromptEvent) {
                alert("On iPhone, use Share and then Add to Home Screen.");
                return;
            }
            installPromptEvent.prompt();
            installPromptEvent.userChoice.finally(function () {
                installPromptEvent = null;
                installBtn.classList.add("hidden");
            });
        });
    }

    function setupServiceWorker() {
        var swUrl = body.dataset.swUrl;
        if (!swUrl || !("serviceWorker" in navigator)) return;
        navigator.serviceWorker.register(swUrl).catch(function () {});
    }

    function checkAssignedTripUpdates() {
        if (!assignmentStateUrl || document.hidden) return;
        fetch(assignmentStateUrl, { credentials: "same-origin" })
            .then(function (r) {
                if (!r.ok) throw new Error("assignment state failed");
                return r.json();
            })
            .then(function (state) {
                if (!previousAssignmentState) {
                    previousAssignmentState = state;
                    updateNotificationBadge(state.notification_count || 0);
                    renderNotificationPanel(state);
                    return;
                }
                var hasNewAssignment =
                    Number(state.assigned_count || 0) > Number(previousAssignmentState.assigned_count || 0) ||
                    (state.latest_assigned_trip_id &&
                        state.latest_assigned_trip_id !== previousAssignmentState.latest_assigned_trip_id);
                var hasNewMessage =
                    Number(state.unread_message_count || 0) > Number(previousAssignmentState.unread_message_count || 0) ||
                    (state.latest_message_id && state.latest_message_id !== previousAssignmentState.latest_message_id);
                var hasFuelApproval =
                    state.latest_approved_fuel_id &&
                    state.latest_approved_fuel_id !== previousAssignmentState.latest_approved_fuel_id;
                updateNotificationBadge(state.notification_count || 0);
                renderNotificationPanel(state);
                if (hasNewAssignment) {
                    showToast("New trip assigned: " + (state.latest_assigned_order || "Trip"), "/transport/driver/trips/");
                    refreshDashboardStats();
                }
                if (hasNewMessage) {
                    showToast("New message from " + (state.latest_message_sender || "support"), "/transport/driver/messages/");
                    if (currentTab === "messages") {
                        refreshMessageThread();
                    }
                }
                if (hasFuelApproval) {
                    showToast("Fuel request approved for " + (state.latest_approved_fuel_trip || "your trip"), "/transport/driver/fuel/");
                }
                previousAssignmentState = state;
            })
            .catch(function () {});
    }

    function refreshMessageThread() {
        var thread = document.getElementById("driver-message-thread");
        if (!thread || currentTab !== "messages" || document.hidden || !messageThreadUrl || hasActiveFormFocus()) return;
        fetch(messageThreadUrl, { credentials: "same-origin" })
            .then(function (r) {
                if (!r.ok) throw new Error("thread refresh failed");
                return r.text();
            })
            .then(function (html) {
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, "text/html");
                var incoming = doc.querySelector("#driver-message-thread-inner");
                if (!incoming) return;

                var existingIds = {};
                thread.querySelectorAll("[data-message-id]").forEach(function (node) {
                    existingIds[node.getAttribute("data-message-id")] = true;
                });

                var newNodes = incoming.querySelectorAll("[data-message-id]");
                if (!thread.querySelector("[data-message-id]")) {
                    thread.innerHTML = incoming.innerHTML;
                    scrollMessageThread();
                    return;
                }

                newNodes.forEach(function (node) {
                    var id = node.getAttribute("data-message-id");
                    if (id && !existingIds[id]) {
                        thread.insertAdjacentElement("beforeend", node.cloneNode(true));
                    }
                });
            })
            .catch(function () {});
    }

    function scrollMessageThread() {
        var thread = document.getElementById("driver-message-thread");
        if (!thread) return;
        thread.scrollTop = thread.scrollHeight;
    }

    document.addEventListener("click", function (event) {
        var notificationBtn = event.target.closest("#notification-button");
        if (notificationBtn) {
            event.preventDefault();
            var panel = document.getElementById("driver-notification-panel");
            var profileMenu = document.getElementById("driver-profile-menu");
            if (profileMenu) profileMenu.classList.add("hidden");
            if (panel) {
                panel.classList.toggle("hidden");
                notificationPanelOpen = !panel.classList.contains("hidden");
            }
            return;
        }

        var profileBtn = event.target.closest("#driver-profile-button");
        if (profileBtn) {
            event.preventDefault();
            var menu = document.getElementById("driver-profile-menu");
            var notificationPanel = document.getElementById("driver-notification-panel");
            if (notificationPanel) notificationPanel.classList.add("hidden");
            if (menu) menu.classList.toggle("hidden");
            return;
        }

        var notificationLink = event.target.closest("[data-driver-notification-link]");
        if (notificationLink) {
            closePanels();
            var targetTab = notificationLink.dataset.driverTab;
            if (targetTab && partialUrls[targetTab] && window.htmx && typeof window.htmx.ajax === "function") {
                event.preventDefault();
                currentTab = targetTab;
                window.htmx.ajax("GET", partialUrls[targetTab], {
                    target: "#driver-content",
                    swap: "innerHTML transition:true"
                });
                setActiveDriverTab(targetTab);
            }
            return;
        }

        var tab = event.target.closest(".driver-tab");
        if (tab) {
            closePanels();
            currentTab = tab.dataset.tab || "dashboard";
            setActiveDriverTab(currentTab);
            return;
        }

        if (!event.target.closest("#driver-notification-panel") && !event.target.closest("#driver-profile-menu")) {
            closePanels();
        }
    });

    document.body.addEventListener("driver-toast", function (event) {
        if (!event.detail) return;
        showToast(event.detail.message, event.detail.href || null);
    });

    document.body.addEventListener("driver-set-tab", function (event) {
        if (!event.detail || !event.detail.tab) return;
        currentTab = event.detail.tab;
        setActiveDriverTab(currentTab);
    });

    document.body.addEventListener("htmx:beforeRequest", function (event) {
        if (event.target && event.target.id === "driver-content") {
            setLoading(true);
        }
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        if (!event.target || event.target.id !== "driver-content") return;
        setLoading(false);
        var section = event.target.firstElementChild && event.target.firstElementChild.dataset
            ? event.target.firstElementChild.dataset.section
            : null;
        if (section) {
            currentTab = section;
            setActiveDriverTab(section);
        }
        scrollMessageThread();
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        if (event.target && event.target.id === "driver-message-thread") {
            scrollMessageThread();
        }
    });

    document.body.addEventListener("htmx:responseError", function () {
        setLoading(false);
        showToast("Something went wrong. Please try again.");
    });

    document.body.addEventListener("submit", function (event) {
        var form = event.target.closest("form[data-driver-disable]");
        if (!form) return;
        var buttons = form.querySelectorAll("button[type='submit']");
        buttons.forEach(function (button) {
            button.disabled = true;
            button.classList.add("opacity-70");
        });
    });

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            refreshDashboardStats();
            checkAssignedTripUpdates();
            refreshMessageThread();
        }
    });

    document.addEventListener("focusin", function (event) {
        if (event.target && event.target.matches("input, textarea, select")) {
            pauseLiveUpdates(30000);
        }
    });

    document.addEventListener("input", function (event) {
        if (event.target && event.target.matches("input, textarea, select")) {
            pauseLiveUpdates(30000);
        }
    });

    setActiveDriverTab(currentTab);
    setupPwaInstall();
    setupServiceWorker();
    checkAssignedTripUpdates();
    if (isSpa) {
        setInterval(checkAssignedTripUpdates, 8000);
        setInterval(refreshDashboardStats, 15000);
        setInterval(refreshMessageThread, 5000);
    }
})();
