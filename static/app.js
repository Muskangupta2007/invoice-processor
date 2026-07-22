/* ==========================================================================
   INVOICESYNC APPLICATION CLIENT SCRIPT (AUTH, INTERACTIVE PORTS & REPORTS)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // Current application state
    const state = {
        invoices: [], 
        reports: {},
        settings: {},
        settingsPassword: "",
        activeTab: "dashboard",
        activeCompany: "SK Agro",      // Active selected company
        activeDocType: "Invoice",     // Active selected module (Invoice/Challan)
        companySelected: false,       // Tracks if user has entered a company workspace
        currentUploadedData: null,    
        vendorChart: null
    };

    // --- DOM ELEMENT REFERENCES ---
    const appWrapper = document.getElementById("app-wrapper");
    const loginScreen = document.getElementById("login-screen");
    const loginForm = document.getElementById("login-form");
    const loginUsername = document.getElementById("login-username");
    const loginPassword = document.getElementById("login-password");
    const logoutBtn = document.getElementById("logout-btn");

    const menuItems = document.querySelectorAll(".sidebar-menu .menu-item");
    const tabContents = document.querySelectorAll(".tab-content");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    const themeToggle = document.getElementById("theme-toggle");
    
    // Status indicators
    const geminiStatus = document.getElementById("gemini-status");
    const teamsStatus = document.getElementById("teams-status");

    // Portal Views
    const portalView = document.getElementById("portal-view");
    const workspaceView = document.getElementById("workspace-view");
    const enterWorkspaceBtns = document.querySelectorAll(".enter-workspace-btn");
    const backToPortalBtn = document.getElementById("back-to-portal-btn");
    const workspaceTitle = document.getElementById("workspace-title");
    const workspaceSubtitle = document.getElementById("workspace-subtitle");
    const workspaceModuleSelect = document.getElementById("workspace-module-select");

    // Action Dropdown Split Buttons (Header)
    const openExcelDropdownBtn = document.getElementById("open-excel-dropdown-btn");
    const openExcelMenu = document.getElementById("open-excel-menu");
    const exportExcelDropdownBtn = document.getElementById("export-excel-dropdown-btn");
    const exportExcelMenu = document.getElementById("export-excel-menu");

    // Synchronized Workspace Badges
    const ledgerCompanyBadge = document.getElementById("ledger-company-badge");
    const uploadCompanyBadge = document.getElementById("upload-company-badge");

    // Interactive Stats Cards (Dashboard)
    const cardTotalDocs = document.getElementById("card-total-docs");
    const cardVolume = document.getElementById("card-volume");
    const cardPendingMrn = document.getElementById("card-pending-mrn");
    const cardSequenceGaps = document.getElementById("card-sequence-gaps");
    const cardPendingEway = document.getElementById("card-pending-eway");
    const cardWorkOrder = document.getElementById("card-work-order");

    // Scoped Stats Numbers
    const statTotalTitle = document.getElementById("stat-total-title");
    const statTotalInvoices = document.getElementById("stat-total-invoices");
    const statTotalAmount = document.getElementById("stat-total-amount");
    const statPendingTitle = document.getElementById("stat-pending-title");
    const statPendingMrns = document.getElementById("stat-pending-mrns");
    const statSequenceGaps = document.getElementById("stat-sequence-gaps");
    const statPendingEway = document.getElementById("stat-pending-eway");
    const statWorkOrderPos = document.getElementById("stat-work-order-pos");
    
    // Scoped Action Center Elements
    const sequenceAuditTitle = document.getElementById("sequence-audit-title");
    const missingActionTitle = document.getElementById("missing-action-title");
    const sequenceGapsList = document.getElementById("sequence-gaps-list");
    const missingMrnsList = document.getElementById("missing-mrns-list");
    const ewayDivider = document.getElementById("eway-divider");
    const ewayAlertSection = document.getElementById("eway-alert-section");
    const ewayBillsList = document.getElementById("eway-bills-list");
    
    // Ledger Controls & Table
    const ledgerSearch = document.getElementById("ledger-search");
    const ledgerModuleFilter = document.getElementById("ledger-module-filter");
    const ledgerMrnFilter = document.getElementById("ledger-mrn-filter");
    const refreshLedgerBtn = document.getElementById("refresh-ledger-btn");
    const ledgerThead = document.getElementById("ledger-thead");
    const ledgerBody = document.getElementById("ledger-body");

    // Upload elements
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const uploadDocType = document.getElementById("upload-doc-type");
    const uploadStatus = document.getElementById("upload-status");
    const statusFilename = document.getElementById("status-filename");
    const statusProgressFill = document.getElementById("status-progress-fill");
    const statusMessage = document.getElementById("status-message");
    const uploadReview = document.getElementById("upload-review");
    const reviewFieldsContainer = document.getElementById("review-fields-container");
    const cancelReviewBtn = document.getElementById("cancel-review-btn");
    const saveReviewBtn = document.getElementById("save-review-btn");

    // Settings elements
    const settingsAdminUsername = document.getElementById("settings-admin-username");
    const settingsAdminPassword = document.getElementById("settings-admin-password");
    const settingsAzureEndpoint = document.getElementById("settings-azure-endpoint");
    const settingsAzureKey = document.getElementById("settings-azure-key");
    const settingsExcelDir = document.getElementById("settings-excel-dir");
    const settingsTeamsWebhook = document.getElementById("settings-teams-webhook");
    const testTeamsBtn = document.getElementById("test-teams-btn");
    const saveSettingsBtn = document.getElementById("save-settings-btn");

    // Google Sheets Settings elements
    const settingsGsheetUrlSkAgro = document.getElementById("settings-gsheet-url-sk-agro");
    const settingsGsheetSyncUrlSkAgro = document.getElementById("settings-gsheet-sync-url-sk-agro");
    const settingsGsheetUrlSkElectricals = document.getElementById("settings-gsheet-url-sk-electricals");
    const settingsGsheetSyncUrlSkElectricals = document.getElementById("settings-gsheet-sync-url-sk-electricals");
    const settingsGsheetUrlTriotech = document.getElementById("settings-gsheet-url-triotech");
    const settingsGsheetSyncUrlTriotech = document.getElementById("settings-gsheet-sync-url-triotech");
    
    const viewGsheetInstructionsBtn = document.getElementById("view-gsheet-instructions-btn");
    const gsheetInstructionsModal = document.getElementById("gsheet-instructions-modal");
    const closeGsheetModal = document.getElementById("close-gsheet-modal");
    const closeGsheetInstructionsBtn = document.getElementById("close-gsheet-instructions-btn");
    const copyGsheetCodeBtn = document.getElementById("copy-gsheet-code-btn");
    const gsheetScriptCode = document.getElementById("gsheet-script-code");

    // Modals
    const duplicateModal = document.getElementById("duplicate-modal");
    const closeDupModal = document.getElementById("close-dup-modal");
    const dupInvoiceNo = document.getElementById("dup-invoice-no");
    const dupComparisonBody = document.getElementById("dup-comparison-body");
    const dupSkipBtn = document.getElementById("dup-skip-btn");
    const dupReplaceBtn = document.getElementById("dup-replace-btn");

    const editModal = document.getElementById("edit-modal");
    const closeEditModal = document.getElementById("close-edit-modal");
    const editForm = document.getElementById("edit-form");
    const editInvoiceNo = document.getElementById("edit-invoice-no");
    const editMrnStatus = document.getElementById("edit-mrn-status");
    const editMrnDate = document.getElementById("edit-mrn-date");
    const editMrnNo = document.getElementById("edit-mrn-no");
    const editRemarks = document.getElementById("edit-remarks");
    const editMrnSection = document.getElementById("edit-mrn-section");
    const editCancelBtn = document.getElementById("edit-cancel-btn");
    
    // Challan Specific Edit Modal Fields
    const editChallanFields = document.getElementById("edit-challan-fields");
    const editItemDescription = document.getElementById("edit-item-description");
    const editDeliverQty = document.getElementById("edit-deliver-qty");
    const editUom = document.getElementById("edit-uom");
    const editUnitPrice = document.getElementById("edit-unit-price");
    const editPoQty = document.getElementById("edit-po-qty");
    const editPoStatus = document.getElementById("edit-po-status");
    const editInvoiceNoVal = document.getElementById("edit-invoice-no-val");
    const editInvoiceItemDescription = document.getElementById("edit-invoice-item-description");
    const editInvoiceItemDescGroup = document.getElementById("edit-invoice-item-desc-group");

    // Toast
    const toastNotification = document.getElementById("toast-notification");
    const toastIcon = document.getElementById("toast-icon");
    const toastMessage = document.getElementById("toast-message");

    // Tab labels meta
    const tabMetadata = {
        dashboard: { title: "Dashboard Hub", subtitle: "Enter a company portal to access dedicated operations workspaces." },
        invoices: { title: "Document Ledger", subtitle: "Separate Excel-synced database sheets for each company." },
        upload: { title: "Upload Center", subtitle: "Ingest new scanned invoices or delivery challans via Azure AI." },
        settings: { title: "System Configuration", subtitle: "Manage Azure configurations, OneDrive sync paths, and Teams." }
    };

    // --- SECURE AUTHORIZATION WRAPPER ---
    
    function getAuthToken() {
        return localStorage.getItem("auth_token") || "";
    }

    function getAuthHeaders(jsonContentType = true) {
        const headers = {
            "Authorization": `Bearer ${getAuthToken()}`
        };
        if (jsonContentType) {
            headers["Content-Type"] = "application/json";
        }
        return headers;
    }

    function getSettingsHeaders(jsonContentType = true) {
        const headers = {
            "Authorization": `Bearer ${state.settingsPassword || ""}`
        };
        if (jsonContentType) {
            headers["Content-Type"] = "application/json";
        }
        return headers;
    }

    function checkAuthResponse(res) {
        if (res.status === 401) {
            localStorage.removeItem("auth_token");
            showLoginScreen();
            throw new Error("Unauthorized Access Redirecting to Login.");
        }
        return res;
    }

    function showLoginScreen() {
        loginScreen.style.display = "flex";
        appWrapper.style.display = "none";
    }

    function hideLoginScreen() {
        loginScreen.style.display = "none";
        appWrapper.style.display = "flex";
    }

    // --- LOGIN FORM HANDLER ---
    
    [loginUsername, loginPassword].forEach(input => {
        if (input) {
            input.addEventListener("input", () => {
                loginUsername.classList.remove("input-error");
                loginPassword.classList.remove("input-error");
                const loginErrorAlert = document.getElementById("login-error-alert");
                if (loginErrorAlert) loginErrorAlert.style.display = "none";
            });
        }
    });

    loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const loginErrorAlert = document.getElementById("login-error-alert");
        const loginErrorText = document.getElementById("login-error-text");
        const loginBox = document.querySelector(".login-box");
        
        if (loginErrorAlert) loginErrorAlert.style.display = "none";
        loginUsername.classList.remove("input-error");
        loginPassword.classList.remove("input-error");
        if (loginBox) loginBox.classList.remove("shake");

        const username = loginUsername.value.trim();
        const password = loginPassword.value.trim();
        
        fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        })
        .then(async res => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.status === "error") {
                const errMsg = data.message || "Invalid Username or Password.";
                
                // Display error alert banner
                if (loginErrorAlert && loginErrorText) {
                    loginErrorText.textContent = errMsg;
                    loginErrorAlert.style.display = "flex";
                }
                
                // Highlight input fields with red error border
                loginUsername.classList.add("input-error");
                loginPassword.classList.add("input-error");
                
                // Trigger card shake animation for clear visual feedback
                if (loginBox) {
                    void loginBox.offsetWidth; // Force reflow
                    loginBox.classList.add("shake");
                }
                
                // Focus & select password for immediate correction
                loginPassword.focus();
                loginPassword.select();
                
                showToast(errMsg, "danger");
                throw new Error(errMsg);
            }
            return data;
        })
        .then(data => {
            if (data.status === "success") {
                localStorage.setItem("auth_token", data.token);
                if (loginErrorAlert) loginErrorAlert.style.display = "none";
                loginUsername.classList.remove("input-error");
                loginPassword.classList.remove("input-error");
                hideLoginScreen();
                showToast("Welcome back! Signed in successfully.");
                switchTab("dashboard");
            }
        })
        .catch(err => {
            console.error("Login request failed:", err);
            const isAuthError = err.message && (err.message.includes("Invalid") || err.message.includes("attempt(s)") || err.message.includes("locked"));
            if (!isAuthError) {
                const errMsg = "Unable to connect to server. Please check your network connection.";
                if (loginErrorAlert && loginErrorText) {
                    loginErrorText.textContent = errMsg;
                    loginErrorAlert.style.display = "flex";
                }
                loginUsername.classList.add("input-error");
                loginPassword.classList.add("input-error");
                if (loginBox) {
                    void loginBox.offsetWidth;
                    loginBox.classList.add("shake");
                }
                showToast(errMsg, "danger");
            }
        });
    });


    logoutBtn.addEventListener("click", () => {
        if (confirm("Are you sure you want to sign out?")) {
            localStorage.removeItem("auth_token");
            state.settingsPassword = "";
            showLoginScreen();
            showToast("Signed out successfully.");
        }
    });

    // --- TAB ROUTING ---
    
    function switchTab(tabId) {
        if (!getAuthToken()) {
            showLoginScreen();
            return;
        }

        if (tabId === "settings" && !state.settingsPassword) {
            openSettingsAuthModal();
            return;
        }

        state.activeTab = tabId;
        
        menuItems.forEach(item => {
            if (item.getAttribute("data-tab") === tabId) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        tabContents.forEach(content => {
            const contentId = content.id.replace("tab-", "");
            if (contentId === tabId) {
                content.classList.add("active");
            } else {
                content.classList.remove("active");
            }
        });

        const meta = tabMetadata[tabId] || { title: "Overview", subtitle: "" };
        pageTitle.innerText = meta.title;
        pageSubtitle.innerText = meta.subtitle;

        if (state.activeCompany) {
            if (ledgerCompanyBadge) ledgerCompanyBadge.innerText = state.activeCompany;
            if (uploadCompanyBadge) uploadCompanyBadge.innerText = state.activeCompany;
        }

        if (tabId === "dashboard") {
            if (state.companySelected) {
                portalView.style.display = "none";
                workspaceView.style.display = "block";
                workspaceModuleSelect.value = state.activeDocType;
                updateWorkspaceLabels();
                fetchData();
            } else {
                portalView.style.display = "block";
                workspaceView.style.display = "none";
            }
        } else if (tabId === "invoices") {
            ledgerModuleFilter.value = state.activeDocType;
            fetchLedger();
        } else if (tabId === "settings") {
            fetchSettings();
        }
    }

    menuItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = item.getAttribute("data-tab");
            switchTab(tabId);
        });
    });

    // --- COMPANY WORKSPACE PORTAL TRANSITIONS ---
    
    enterWorkspaceBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const company = btn.getAttribute("data-company");
            enterWorkspace(company);
        });
    });

    function enterWorkspace(company) {
        state.activeCompany = company;
        state.companySelected = true;
        
        portalView.style.display = "none";
        workspaceView.style.display = "block";
        
        updateWorkspaceLabels();
        fetchData();
    }

    function leaveWorkspace() {
        state.companySelected = false;
        
        portalView.style.display = "block";
        workspaceView.style.display = "none";
        
        pageTitle.innerText = tabMetadata.dashboard.title;
        pageSubtitle.innerText = tabMetadata.dashboard.subtitle;
    }

    backToPortalBtn.addEventListener("click", leaveWorkspace);

    workspaceModuleSelect.addEventListener("change", () => {
        state.activeDocType = workspaceModuleSelect.value;
        updateWorkspaceLabels();
        fetchData();
    });

    function updateWorkspaceLabels() {
        workspaceTitle.innerText = `${state.activeCompany} Operations Workspace`;
        workspaceSubtitle.innerText = `Verify extracted ${state.activeDocType.toLowerCase()}s, gaps, and pending entries.`;
        
        pageTitle.innerText = `${state.activeCompany} Workspace`;
        pageSubtitle.innerText = `Ingestion workspace details for ${state.activeCompany}.`;
        
        statTotalTitle.innerText = state.activeDocType === 'Invoice' ? "TOTAL INVOICES" : "TOTAL CHALLANS";
        statPendingTitle.innerText = state.activeDocType === 'Invoice' ? "PENDING MRNS" : "PENDING POS";
        
        const missingActionLabel = document.getElementById("missing-action-label");
        if (missingActionLabel) {
            missingActionLabel.innerText = state.activeDocType === 'Invoice' ? "Pending MRN List" : "Pending PO List";
        }

        if (state.activeDocType === 'Invoice') {
            if (cardPendingEway) cardPendingEway.style.display = "flex";
            if (cardWorkOrder) cardWorkOrder.style.display = "none";
        } else {
            if (cardPendingEway) cardPendingEway.style.display = "none";
            if (cardWorkOrder) cardWorkOrder.style.display = "flex";
        }
    }

    // --- ACTION DROPDOWN SPLIT BUTTONS HANDLERS ---
    
    document.querySelectorAll(".dropdown-action-trigger").forEach(trigger => {
        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            const parent = trigger.parentElement;
            const menu = parent.querySelector(".dropdown-action-menu");
            
            document.querySelectorAll(".dropdown-action-menu").forEach(m => {
                if (m !== menu) m.classList.remove("show");
            });
            
            menu.classList.toggle("show");
        });
    });

    document.addEventListener("click", () => {
        document.querySelectorAll(".dropdown-action-menu").forEach(m => m.classList.remove("show"));
    });

    // --- OPEN IN EXCEL (LOCAL SYSTEM ONLY) ---
    document.querySelectorAll(".open-excel-opt").forEach(opt => {
        opt.addEventListener("click", (e) => {
            e.preventDefault();
            const fileType = opt.getAttribute("data-type");
            const label = fileType === 'work_order' ? "Work Order POs" : (fileType === 'pending' ? "Pending List" : "Main Ledger");
            
            // If Google Sheets is configured for the active company, open the live sheet in a new tab instead of downloading
            const companyKey = state.activeCompany.toLowerCase().replace(' ', '_');
            const gsheetUrl = state.settings[`gsheet_url_${companyKey}`];
            if (gsheetUrl) {
                showToast(`Opening ${state.activeCompany} live Google Sheet...`);
                window.open(gsheetUrl, '_blank');
                return;
            }
            
            // Detect if browser is remote or local
            const localHostnames = ['localhost', '127.0.0.1', 'invoice.local', 'muskan'];
            const isLocalClient = localHostnames.includes(window.location.hostname.toLowerCase());

            if (!isLocalClient) {
                // Remote clients should download directly to their own device
                showToast(`Downloading ${state.activeCompany} ${label} workbook...`);
                const tokenStr = `?token=${encodeURIComponent(getAuthToken())}`;
                const downloadUrl = `/api/download-excel/${encodeURIComponent(state.activeCompany)}/${fileType}${tokenStr}`;
                window.location.href = downloadUrl;
                return;
            }

            showToast(`Launching ${state.activeCompany} ${label} workbook...`);

            fetch(`/api/open-excel/${encodeURIComponent(state.activeCompany)}/${fileType}?client_host=${encodeURIComponent(window.location.hostname)}`, { 
                method: "POST",
                headers: getAuthHeaders(true)
            })
            .then(checkAuthResponse)
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    showToast(data.message);
                } else if (data.status === "download") {
                    showToast(data.message || "Downloading file...");
                    window.location.href = data.url;
                } else {
                    showToast(data.message, "danger");
                }
            })
            .catch(err => {
                console.error("Open Excel error:", err);
                showToast("Failed to launch Microsoft Excel. Downloading instead...", "warning");
                // Fallback to direct download
                const tokenStr = `?token=${encodeURIComponent(getAuthToken())}`;
                const downloadUrl = `/api/download-excel/${encodeURIComponent(state.activeCompany)}/${fileType}${tokenStr}`;
                window.location.href = downloadUrl;
            });
        });
    });

    // --- EXPORT LEDGER (DIRECT DOWNLOAD TO DEVICE) ---
    document.querySelectorAll(".export-excel-opt").forEach(opt => {
        opt.addEventListener("click", (e) => {
            e.preventDefault();
            const fileType = opt.getAttribute("data-type");
            const label = fileType === 'work_order' ? "Work Order POs" : (fileType === 'pending' ? "Pending List" : "Main Ledger");
            
            showToast(`Downloading ${state.activeCompany} ${label} workbook...`);

            const tokenStr = `?token=${encodeURIComponent(getAuthToken())}`;
            const downloadUrl = `/api/download-excel/${encodeURIComponent(state.activeCompany)}/${fileType}${tokenStr}`;
            
            window.location.href = downloadUrl;
        });
    });

    // --- INTERACTIVE DOUBLE-CLICK EXCEL REPORTING ---
    
    function triggerReportDownload(reportType) {
        const tokenStr = `&token=${encodeURIComponent(getAuthToken())}`;
        let url = `/api/download-report/${encodeURIComponent(state.activeCompany)}/${reportType}?doc_type=${encodeURIComponent(state.activeDocType)}${tokenStr}`;
        if (reportType === 'main') {
            url = `/api/download-excel/${encodeURIComponent(state.activeCompany)}/main?token=${encodeURIComponent(getAuthToken())}`;
        }
        
        showToast(`Generating and downloading Excel report...`);
        window.location.href = url;
    }

    cardTotalDocs.addEventListener("dblclick", () => triggerReportDownload("main"));
    cardVolume.addEventListener("dblclick", () => triggerReportDownload("volume"));
    cardPendingMrn.addEventListener("dblclick", () => {
        const type = state.activeDocType === 'Invoice' ? "pending_mrn" : "pending_po";
        triggerReportDownload(type);
    });
    cardSequenceGaps.addEventListener("dblclick", () => triggerReportDownload("sequence_gap"));
    cardPendingEway.addEventListener("dblclick", () => triggerReportDownload("pending_eway"));
    if (cardWorkOrder) cardWorkOrder.addEventListener("dblclick", () => triggerReportDownload("work_order"));

    // --- 3-WAY THEME SYSTEM (Dark -> Light -> Soft Pink) ---
    function applyTheme(themeName) {
        document.body.classList.remove("dark-mode", "light-mode", "pink-mode");
        
        if (themeName === "light") {
            document.body.classList.add("light-mode");
            themeToggle.innerHTML = '<i class="fa-solid fa-sun" style="color: #f59e0b;"></i>';
            themeToggle.title = "Theme: Light (Click for Soft Pink Theme)";
        } else if (themeName === "pink") {
            document.body.classList.add("pink-mode");
            themeToggle.innerHTML = '<i class="fa-solid fa-heart" style="color: #f43f5e;"></i>';
            themeToggle.title = "Theme: Soft Pink (Click for Dark Theme)";
        } else {
            document.body.classList.add("dark-mode");
            themeToggle.innerHTML = '<i class="fa-solid fa-moon" style="color: #818cf8;"></i>';
            themeToggle.title = "Theme: Dark (Click for Light Theme)";
        }
        localStorage.setItem("invosync_theme", themeName);
        if (state.vendorChart) drawChart();
    }

    // Load saved theme preference on boot
    const savedTheme = localStorage.getItem("invosync_theme") || "dark";
    applyTheme(savedTheme);

    themeToggle.addEventListener("click", () => {
        if (document.body.classList.contains("dark-mode")) {
            applyTheme("light");
            showToast("Switched to Light Theme");
        } else if (document.body.classList.contains("light-mode")) {
            applyTheme("pink");
            showToast("Switched to Soft Pink Theme 🌸");
        } else {
            applyTheme("dark");
            showToast("Switched to Dark Theme");
        }
    });

    function onLedgerFiltersChange() {
        state.activeDocType = ledgerModuleFilter.value;
        fetchLedger();
    }
    ledgerModuleFilter.addEventListener("change", onLedgerFiltersChange);

    // --- TOAST NOTIFICATIONS ---
    
    let toastTimeout = null;
    function showToast(message, type = "success") {
        clearTimeout(toastTimeout);
        toastMessage.innerText = message;
        toastNotification.className = "toast";
        toastNotification.classList.add(`toast-${type}`);
        
        if (type === "success") {
            toastIcon.className = "fa-solid fa-circle-check";
        } else if (type === "warning") {
            toastIcon.className = "fa-solid fa-circle-exclamation";
        } else {
            toastIcon.className = "fa-solid fa-circle-xmark";
        }

        toastNotification.style.display = "flex";
        
        toastTimeout = setTimeout(() => {
            toastNotification.style.animation = "fadeInModal 0.2s reverse forwards";
            setTimeout(() => {
                toastNotification.style.display = "none";
                toastNotification.style.animation = "";
            }, 200);
        }, 3500);
    }

    function formatCurrency(val) {
        if (val === null || val === undefined) return "₹0.00";
        const num = parseFloat(val);
        if (isNaN(num)) return "₹0.00";
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(num);
    }

    // --- FETCH DATA (DASHBOARD) ---
    
    function fetchData() {
        if (!getAuthToken()) {
            showLoginScreen();
            return;
        }

        console.log("[DEBUG] fetchData called | company:", state.activeCompany, "| docType:", state.activeDocType);

        // Immediately clear state so previous company/module data doesn't linger
        state.invoices = [];
        state.reports = null;

        // Immediately sync UI section visibility & labels to match activeDocType
        const cardPendingEway = document.getElementById("card-pending-eway");
        const ewayDivider = document.getElementById("eway-divider");
        const ewayAlertSection = document.getElementById("eway-alert-section");
        const missingLabel = document.getElementById("missing-action-label");
        const statPendingTitle = document.querySelector("#card-pending-mrns h3");

        if (state.activeDocType === 'Invoice') {
            if (cardPendingEway) cardPendingEway.style.display = "flex";
            if (ewayDivider) ewayDivider.style.display = "block";
            if (ewayAlertSection) ewayAlertSection.style.display = "block";
            if (missingLabel) missingLabel.innerText = "Pending MRN List";
            if (statPendingTitle) statPendingTitle.innerText = "PENDING MRNS";
        } else {
            if (cardPendingEway) cardPendingEway.style.display = "none";
            if (ewayDivider) ewayDivider.style.display = "none";
            if (ewayAlertSection) ewayAlertSection.style.display = "none";
            if (missingLabel) missingLabel.innerText = "Pending PO List";
            if (statPendingTitle) statPendingTitle.innerText = "PENDING POS";
        }

        fetch(`/api/invoices?company=${encodeURIComponent(state.activeCompany)}&doc_type=${encodeURIComponent(state.activeDocType)}`, {
            headers: getAuthHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            console.log("[DEBUG] /api/invoices response:", data.status, "| count:", data.invoices ? data.invoices.length : 'N/A');
            if (data.status === "success") {
                state.invoices = data.invoices || [];
                state.reports = data.reports || null;
                updateDashboardStats(data);
                renderAlertLists();
                updateReportsStats();
                drawChart();
            } else {
                console.error("[DEBUG] /api/invoices returned non-success:", data);
            }
        })
        .catch(err => {
            console.error("[DEBUG] Error fetching invoices:", err);
            setTimeout(() => {
                const currentHash = window.location.hash;
                if (!currentHash || currentHash === "#dashboard" || currentHash === "#") {
                    fetchData();
                }
            }, 3000);
        });

        fetch("/api/settings/status", {
            headers: getAuthHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            geminiStatus.className = data.azure_api_key_configured ? "dot green" : "dot red";
            teamsStatus.className = data.teams_webhook_url ? "dot green" : "dot red";
        })
        .catch(err => console.error("Error fetching settings indicator:", err));
    }

    function setAlertListClass(el, isEmpty) {
        if (!el) return;
        const isCollapsed = el.classList.contains("collapsed");
        el.className = "alert-list" + (isEmpty ? " empty-state" : "") + (isCollapsed ? " collapsed" : "");
    }

    function updateDashboardStats(data) {
        statTotalInvoices.innerText = data.invoices.length;
        
        const gaps = data.sequence_check.missing_numbers || [];
        statSequenceGaps.innerText = gaps.length;
        const seqCountEl = document.getElementById("sequence-audit-count");
        if (seqCountEl) seqCountEl.innerText = gaps.length;

        if (gaps.length > 0) {
            setAlertListClass(sequenceGapsList, false);
            sequenceGapsList.innerHTML = gaps.map(gapNo => `
                <div class="alert-item alert-item-warning">
                    <span>Missing sequential ${state.activeDocType}: <strong>${gapNo}</strong></span>
                    <span class="alert-link" onclick="window.location.hash='#upload'; document.querySelector('[data-tab=upload]').click()">Upload Now</span>
                </div>
            `).join("");
        } else {
            setAlertListClass(sequenceGapsList, true);
            sequenceGapsList.innerHTML = `<p>No sequence gaps detected for ${state.activeCompany} ${state.activeDocType}s!</p>`;
        }
    }

    function calculateOverallPoStatusFromList(statuses) {
        if (!statuses || statuses.length === 0) return 'Open';
        const cleaned = statuses.map(s => String(s || '').trim().toUpperCase()).filter(Boolean);
        if (cleaned.length === 0) return 'Open';
        
        if (cleaned.some(s => s === 'OPEN' || s === 'PENDING' || s === '')) {
            return 'Open';
        }
        if (cleaned.some(s => s === 'WORK ORDER' || s === 'WORKORDER')) {
            return 'Work Order';
        }
        if (cleaned.every(s => s === 'CLOSE' || s === 'CLOSED')) {
            return 'Close';
        }
        return 'Open';
    }

    function calculateOverallPoStatusFromDoc(doc) {
        if (!doc) return 'Open';
        const po_stats = (doc.po_status || "").split('\n');
        return calculateOverallPoStatusFromList(po_stats);
    }

    function renderAlertLists() {
        if (!state.invoices) return;

        const missingLabel = document.getElementById("missing-action-label");
        const missingCount = document.getElementById("missing-mrn-count");
        const ewayCount = document.getElementById("eway-bill-count");
        const statPendingTitle = document.querySelector("#card-pending-mrns h3");
        
        const missingMrnsListEl = document.getElementById("missing-mrns-list");
        const ewayBillsListEl = document.getElementById("eway-bills-list");
        if (!missingMrnsListEl || !ewayBillsListEl) return;

        const workorderAlertSection = document.getElementById("workorder-alert-section");
        const workorderDivider = document.getElementById("workorder-divider");
        const workorderCount = document.getElementById("workorder-po-count");
        const workorderPosListEl = document.getElementById("workorder-pos-list");

        if (state.activeDocType === 'Invoice') {
            if (statPendingTitle) statPendingTitle.innerText = "PENDING MRNS";
            if (missingLabel) missingLabel.innerText = "Pending MRN List";
            ewayDivider.style.display = "block";
            ewayAlertSection.style.display = "block";
            if (workorderAlertSection) workorderAlertSection.style.display = "none";
            if (workorderDivider) workorderDivider.style.display = "none";
            
            const missingList = state.invoices.filter(inv =>
                String(inv.mrn_status || '').toUpperCase() !== 'DONE'
            ).sort(docNumberSortKey);
            statPendingMrns.innerText = missingList.length;
            if (missingCount) missingCount.innerText = missingList.length;

            if (missingList.length > 0) {
                setAlertListClass(missingMrnsListEl, false);
                missingMrnsListEl.innerHTML = missingList.map(inv => `
                    <div class="alert-item alert-item-danger">
                        <span>Invoice <strong>${inv.doc_no}</strong> (${inv.bill_to || 'Unknown'}) is missing MRN.</span>
                        <span class="alert-link edit-mrn-trigger" data-doc-no="${inv.doc_no}">Update MRN</span>
                    </div>
                `).join("");

                document.querySelectorAll(".edit-mrn-trigger").forEach(link => {
                    link.addEventListener("click", () => {
                        const docNo = link.getAttribute("data-doc-no");
                        openEditModal(docNo);
                    });
                });
            } else {
                setAlertListClass(missingMrnsListEl, true);
                missingMrnsListEl.innerHTML = `<p>No records with pending MRN status.</p>`;
            }
            
            const pendingEwayList = state.invoices.filter(inv => {
                const isInvoice = String(inv.doc_type || '').toLowerCase() === 'invoice';
                const ewayStatus = String(inv.eway_bill || '').toUpperCase();
                const ewayNo = String(inv.eway_bill_no || '').trim();
                const rawAmtStr = String(inv.amount || '0').replace(/,/g, '').trim();
                const amt = parseFloat(rawAmtStr) || 0;
                if (!isInvoice) return false;
                if (ewayStatus === 'DONE' || ewayStatus === 'N/A') return false;
                if (ewayNo) return false;
                return ewayStatus === 'PENDING' || amt >= 50000;
            });
            statPendingEway.innerText = pendingEwayList.length;
            if (ewayCount) ewayCount.innerText = pendingEwayList.length;

            if (pendingEwayList.length > 0) {
                setAlertListClass(ewayBillsListEl, false);
                ewayBillsListEl.innerHTML = pendingEwayList.map(inv => `
                    <div class="alert-item alert-item-warning" style="display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px;">
                        <span>Invoice <strong>${inv.doc_no}</strong> (${inv.bill_to || 'Unknown'}) is ≥ ₹50,000 but missing E-Way Bill No.</span>
                        <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                            <input type="text" class="eway-inline-input" data-doc-no="${inv.doc_no}" placeholder="Enter E-Way Bill No" style="padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-color); background: rgba(255,255,255,0.05); color: var(--text-color); width: 150px; font-size: 0.85rem;">
                            <button class="btn btn-primary save-eway-inline-btn" data-doc-no="${inv.doc_no}" style="padding: 4px 10px; font-size: 0.85rem; border-radius: 4px; height: 28px; line-height: 1;">Save</button>
                        </div>
                    </div>
                `).join("");

                document.querySelectorAll(".save-eway-inline-btn").forEach(btn => {
                    btn.addEventListener("click", () => {
                        const docNo = btn.getAttribute("data-doc-no");
                        const inputEl = document.querySelector(`.eway-inline-input[data-doc-no="${CSS.escape(docNo)}"]`);
                        const ewayVal = inputEl ? inputEl.value.trim() : "";
                        
                        if (!ewayVal) {
                            showToast("Please enter a valid E-Way Bill number.", "warning");
                            return;
                        }
                        
                        showToast(`Saving E-Way Bill for invoice ${docNo}...`);

                        const targetInv = state.invoices.find(inv => inv.doc_no === docNo);
                        if (targetInv) {
                            targetInv.eway_bill_no = ewayVal;
                            targetInv.eway_bill = 'DONE';
                        }
                        renderAlertLists();
                        
                        const comp = state.activeCompany;
                        const docType = 'Invoice';
                        
                        fetch(`/api/invoices/${encodeURIComponent(comp)}/${encodeURIComponent(docType)}/${encodeURIComponent(docNo)}`, {
                            method: "PUT",
                            headers: getAuthHeaders(true),
                            body: JSON.stringify({ eway_bill: ewayVal })
                        })
                        .then(checkAuthResponse)
                        .then(res => res.json())
                        .then(data => {
                            if (data.status === "success") {
                                showToast(`E-Way Bill for ${docNo} updated successfully!`);
                                fetchData();
                            } else {
                                showToast(data.message, "danger");
                                fetchData();
                            }
                        })
                        .catch(err => {
                            console.error("Error saving inline E-Way Bill:", err);
                            showToast("Failed to save inline E-Way Bill.", "danger");
                            fetchData();
                        });
                    });
                });
            } else {
                setAlertListClass(ewayBillsListEl, true);
                ewayBillsListEl.innerHTML = `<p>No invoices with pending E-Way bill status.</p>`;
            }
        } else {
            if (statPendingTitle) statPendingTitle.innerText = "PENDING POS";
            if (missingLabel) missingLabel.innerText = "Pending PO List";
            ewayDivider.style.display = "none";
            ewayAlertSection.style.display = "none";
            if (workorderAlertSection) workorderAlertSection.style.display = "block";
            if (workorderDivider) workorderDivider.style.display = "block";
            
            const pendingPoList = state.invoices.filter(inv => {
                const isChallan = String(inv.doc_type || '').toLowerCase() === 'challan';
                if (!isChallan) return false;
                return calculateOverallPoStatusFromDoc(inv) === 'Open';
            }).sort(docNumberSortKey);

            statPendingMrns.innerText = pendingPoList.length;
            if (missingCount) missingCount.innerText = pendingPoList.length;

            if (pendingPoList.length > 0) {
                setAlertListClass(missingMrnsListEl, false);
                missingMrnsListEl.innerHTML = pendingPoList.map(inv => `
                    <div class="alert-item alert-item-danger">
                        <span>Challan <strong>${inv.doc_no}</strong> (PO: ${inv.po_wo_no || 'N/A'}) has Open PO status.</span>
                        <span class="alert-link edit-mrn-trigger" data-doc-no="${inv.doc_no}">Update PO Status</span>
                    </div>
                `).join("");

                document.querySelectorAll(".edit-mrn-trigger").forEach(link => {
                    link.addEventListener("click", () => {
                        const docNo = link.getAttribute("data-doc-no");
                        openEditModal(docNo);
                    });
                });
            } else {
                setAlertListClass(missingMrnsListEl, true);
                missingMrnsListEl.innerHTML = `<p>No delivery challans with pending PO status.</p>`;
            }

            const workOrderList = state.invoices.filter(inv => {
                const isChallan = String(inv.doc_type || '').toLowerCase() === 'challan';
                if (!isChallan) return false;
                return calculateOverallPoStatusFromDoc(inv) === 'Work Order';
            }).sort(docNumberSortKey);

            if (workorderCount) workorderCount.innerText = workOrderList.length;
            if (statWorkOrderPos) statWorkOrderPos.innerText = workOrderList.length;

            if (workorderPosListEl) {
                if (workOrderList.length > 0) {
                    setAlertListClass(workorderPosListEl, false);
                    workorderPosListEl.innerHTML = `
                        <div style="padding: 6px 14px 10px 14px; text-align: right;">
                            <button class="btn btn-secondary btn-sm export-wo-excel-btn" style="font-size: 0.82rem; padding: 4px 10px;">
                                <i class="fa-solid fa-file-excel"></i> Download Work Order Excel Report
                            </button>
                        </div>
                    ` + workOrderList.map(inv => `
                        <div class="alert-item alert-item-info">
                            <span>Challan <strong>${inv.doc_no}</strong> (PO: ${inv.po_wo_no || 'N/A'}) has Work Order PO status.</span>
                            <span class="alert-link edit-mrn-trigger" data-doc-no="${inv.doc_no}">Update PO Status</span>
                        </div>
                    `).join("");

                    const downloadWoBtn = workorderPosListEl.querySelector(".export-wo-excel-btn");
                    if (downloadWoBtn) {
                        downloadWoBtn.addEventListener("click", () => triggerReportDownload("work_order"));
                    }

                    workorderPosListEl.querySelectorAll(".edit-mrn-trigger").forEach(link => {
                        link.addEventListener("click", () => {
                            const docNo = link.getAttribute("data-doc-no");
                            openEditModal(docNo);
                        });
                    });
                } else {
                    setAlertListClass(workorderPosListEl, true);
                    workorderPosListEl.innerHTML = `<p>No delivery challans with Work Order PO status.</p>`;
                }
            }
        }
    }

    function updateReportsStats() {
        if (!state.reports) return;
        statTotalAmount.innerText = formatCurrency(state.reports.total_amt);
        
        if (state.activeDocType === 'Invoice') {
            statPendingMrns.innerText = state.reports.pending_mrn;
            statPendingEway.innerText = state.reports.pending_eway;
        } else {
            statPendingMrns.innerText = state.reports.pending_po;
        }
        renderAlertLists();
    }

    function drawChart() {
        const canvas = document.getElementById("vendorChart");
        if (!canvas) return;

        if (state.vendorChart) {
            state.vendorChart.destroy();
        }

        const isDark = document.body.classList.contains("dark-mode");
        const isPink = document.body.classList.contains("pink-mode");
        const textColor = isPink ? "#9d174d" : (isDark ? "#9ea4c0" : "#6b7280");
        const gridColor = isPink ? "rgba(244, 114, 182, 0.2)" : (isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.05)");

        const chartData = state.reports.by_company || [];
        const labels = chartData.map(item => item.company.length > 18 ? item.company.substring(0, 15) + "..." : item.company);
        const amounts = chartData.map(item => item.amount);

        const ctx = document.getElementById("vendorChart").getContext("2d");
        state.vendorChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels.length > 0 ? labels : ["No Data"],
                datasets: [{
                    label: 'Total Volume (₹)',
                    data: amounts.length > 0 ? amounts : [0],
                    backgroundColor: 'rgba(123, 131, 235, 0.7)',
                    borderColor: '#7b83eb',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Volume: ${formatCurrency(context.parsed.y)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            callback: function(value) {
                                return value >= 100000 ? (value / 100000) + 'L' : value;
                            }
                        }
                    }
                }
            }
        });
    }

    // --- FETCH LEDGER TABLE ---
    
    function fetchLedger() {
        if (!getAuthToken()) {
            showLoginScreen();
            return;
        }

        const comp = state.activeCompany;
        const docType = ledgerModuleFilter.value;

        if (docType === "Challan") {
            ledgerThead.innerHTML = `
                <tr>
                    <th class="col-sno">S.No</th>
                    <th class="col-invoice">Delivery Challan No</th>
                    <th>Item Description</th>
                    <th>Deliver Qty</th>
                    <th>UOM</th>
                    <th>Unit Price</th>
                    <th>Delivery Date</th>
                    <th>Delivery Location</th>
                    <th>PO Status</th>
                    <th>PO Number</th>
                    <th>PO Qty</th>
                    <th>Difference</th>
                    <th>Invoice Number</th>
                    <th>Remarks</th>
                    <th class="col-actions">Actions</th>
                </tr>
            `;
        } else {
            ledgerThead.innerHTML = `
                <tr>
                    <th class="col-sno">S.No</th>
                    <th class="col-invoice">Invoice No</th>
                    <th>Invoice Date</th>
                    <th>Challan No</th>
                    <th>Bill To</th>
                    <th>PO/WO No</th>
                    <th>Item Description</th>
                    <th class="col-amount">Invoice Amt (₹)</th>
                    <th>Eway Bill</th>
                    <th>E way Bill no</th>
                    <th>ASN No</th>
                    <th>Mode of Transp</th>
                    <th>Dock Code</th>
                    <th>Delivery Date</th>
                    <th>Delivery Site</th>
                    <th>MRN Status</th>
                    <th>MRN Date</th>
                    <th>MRN No</th>
                    <th>Remarks</th>
                    <th class="col-actions">Actions</th>
                </tr>
            `;
        }

        // Fast Path: If data is already in state for active company, render instantly
        if (state.invoices && state.invoices.length > 0) {
            const firstDoc = state.invoices[0];
            if (firstDoc && String(firstDoc.company || '').toLowerCase() === String(comp).toLowerCase() && String(firstDoc.doc_type || '').toLowerCase() === String(docType).toLowerCase()) {
                renderLedgerTable(state.invoices, docType);
            } else {
                ledgerBody.innerHTML = `
                    <tr class="table-placeholder">
                        <td colspan="19">
                            <div class="table-loading">
                                <i class="fa-solid fa-spinner fa-spin"></i>
                                <p>Loading ledger entries...</p>
                            </div>
                        </td>
                    </tr>
                `;
            }
        } else {
            ledgerBody.innerHTML = `
                <tr class="table-placeholder">
                    <td colspan="19">
                        <div class="table-loading">
                            <i class="fa-solid fa-spinner fa-spin"></i>
                            <p>Loading ledger entries...</p>
                        </div>
                    </td>
                </tr>
            `;
        }

        fetch(`/api/invoices?company=${encodeURIComponent(comp)}&doc_type=${encodeURIComponent(docType)}`, {
            headers: getAuthHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                state.invoices = data.invoices;
                renderLedgerTable(data.invoices, docType);
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            console.error("Error loading ledger:", err);
            showToast("Failed to connect to backend server.", "danger");
        });
    }

    function calculateDifference(del_qty_str, po_qty_str) {
        del_qty_str = String(del_qty_str || '').trim();
        po_qty_str = String(po_qty_str || '').trim();
        
        if (!del_qty_str && !po_qty_str) return "";
        
        const del_parts = del_qty_str ? del_qty_str.split('\n') : [];
        const po_parts = po_qty_str ? po_qty_str.split('\n') : [];
        
        const max_len = Math.max(del_parts.length, po_parts.length);
        const diffs = [];
        
        for (let i = 0; i < max_len; i++) {
            const d = parseFloat((del_parts[i] || '0').replace(/,/g, '')) || 0;
            const p = parseFloat((po_parts[i] || '0').replace(/,/g, '')) || 0;
            diffs.push(d - p);
        }
        
        return diffs.join('\n');
    }

    function docNumberSortKey(a, b) {
        const getSortParts = (doc) => {
            const docNo = String(doc.doc_no || '').trim();
            const match = docNo.match(/^(.*?)(?:\/|-|_|\b)(\d+)$/);
            if (match) {
                return { prefix: match[1].toLowerCase(), num: parseInt(match[2], 10), docNo: docNo.toLowerCase() };
            }
            const nums = docNo.match(/\d+/g);
            if (nums) {
                const lastNum = parseInt(nums[nums.length - 1], 10);
                const prefix = docNo.substring(0, docNo.lastIndexOf(nums[nums.length - 1]));
                return { prefix: prefix.toLowerCase(), num: lastNum, docNo: docNo.toLowerCase() };
            }
            return { prefix: docNo.toLowerCase(), num: 0, docNo: docNo.toLowerCase() };
        };

        const pa = getSortParts(a);
        const pb = getSortParts(b);

        if (pa.prefix !== pb.prefix) {
            return pa.prefix.localeCompare(pb.prefix);
        }
        if (pa.num !== pb.num) {
            return pa.num - pb.num;
        }
        return pa.docNo.localeCompare(pb.docNo);
    }

    function renderLedgerTable(invoices, docType) {
        const searchTerm = ledgerSearch.value.toLowerCase().trim();
        const mrnFilter = ledgerMrnFilter.value;

        const filtered = invoices.filter(inv => {
            const matchesSearch = 
                String(inv.doc_no).toLowerCase().includes(searchTerm) ||
                String(inv.bill_to).toLowerCase().includes(searchTerm) ||
                String(inv.po_wo_no).toLowerCase().includes(searchTerm) ||
                (inv.item_description && String(inv.item_description).toLowerCase().includes(searchTerm));
                
            const status = String(inv.mrn_status).toUpperCase();
            let matchesMrn = true;
            if (mrnFilter === "pending") {
                matchesMrn = (status !== "DONE");
            } else if (mrnFilter === "done") {
                matchesMrn = (status === "DONE");
            }
            
            return matchesSearch && matchesMrn;
        });

        const colCount = docType === "Challan" ? 15 : 19;

        if (filtered.length === 0) {
            ledgerBody.innerHTML = `
                <tr>
                    <td colspan="${colCount}">
                        <div class="empty-ledger-state">
                            <i class="fa-solid fa-folder-open"></i>
                            <p>No matching document records found.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        const sorted = [...filtered].sort(docNumberSortKey);

        let finalHtml = "";
        
        sorted.forEach((inv, index) => {
            if (docType === "Challan") {
                const descs = (inv.item_description || '').split('\n');
                const qties = (inv.deliver_qty || '').split('\n');
                const uoms = (inv.uom || '').split('\n');
                const prices = (inv.unit_price || '').split('\n');
                const po_qties = (inv.po_qty || '').split('\n');
                const po_statuses = (inv.po_status || '').split('\n');
                
                const numItems = Math.max(descs.length, qties.length, uoms.length, prices.length, po_qties.length, po_statuses.length, 1);
                
                for (let i = 0; i < numItems; i++) {
                    const desc = descs[i] || '';
                    const qty = qties[i] || '';
                    const uom = uoms[i] || '';
                    const price = prices[i] || '';
                    const po_qty = po_qties[i] || '';
                    let itemSt = (po_statuses[i] || '').trim();
                    let itemBadgeClass = "badge-warning";
                    if (!itemSt || itemSt.toUpperCase() === 'OPEN') {
                        itemSt = 'Open';
                        itemBadgeClass = 'badge-warning';
                    } else if (itemSt.toUpperCase() === 'CLOSE' || itemSt.toUpperCase() === 'CLOSED') {
                        itemSt = 'Close';
                        itemBadgeClass = 'badge-success';
                    } else if (itemSt.toUpperCase() === 'WORK ORDER' || itemSt.toUpperCase() === 'WORKORDER') {
                        itemSt = 'Work Order';
                        itemBadgeClass = 'badge-info';
                    } else {
                        itemSt = 'Open';
                        itemBadgeClass = 'badge-warning';
                    }
                    const diff = calculateDifference(qty, po_qty);
                    
                    let rowHtml = '<tr>';
                    
                    if (i === 0) {
                        const overallSt = calculateOverallPoStatusFromDoc(inv);
                        let overallBadgeClass = "badge-warning";
                        if (overallSt === 'Close') overallBadgeClass = "badge-success";
                        else if (overallSt === 'Work Order') overallBadgeClass = "badge-info";

                        rowHtml += `<td rowspan="${numItems}" class="col-sno">${index + 1}</td>`;
                        rowHtml += `<td rowspan="${numItems}" class="col-invoice">
                            <strong>${inv.doc_no || ''}</strong>
                            <div style="margin-top: 4px;"><span class="count-badge ${overallBadgeClass}" title="Overall PO Status">${overallSt}</span></div>
                        </td>`;
                    }
                    
                    // Item level fields (always present in each row)
                    rowHtml += `<td style="text-align: left;"><strong>${i + 1}.</strong> ${desc}</td>`;
                    rowHtml += `<td>${qty}</td>`;
                    rowHtml += `<td>${uom}</td>`;
                    rowHtml += `<td>${price}</td>`;
                    
                    if (i === 0) {
                        rowHtml += `<td rowspan="${numItems}">${inv.delivery_date || ''}</td>`;
                        rowHtml += `<td rowspan="${numItems}">${inv.delivery_site || ''}</td>`;
                    }
                    
                    rowHtml += `<td><span class="count-badge ${itemBadgeClass}">${itemSt}</span></td>`;
                    
                    if (i === 0) {
                        rowHtml += `<td rowspan="${numItems}">${inv.po_wo_no || ''}</td>`;
                    }
                    
                    rowHtml += `<td>${po_qty}</td>`;
                    rowHtml += `<td style="font-weight: 700;">${diff}</td>`;
                    
                    if (i === 0) {
                        rowHtml += `<td rowspan="${numItems}">${inv.invoice_no || ''}</td>`;
                        rowHtml += `
                            <td rowspan="${numItems}">
                                <span class="editable-cell open-edit-btn" data-doc-no="${inv.doc_no}">
                                    ${inv.remarks || '-'}
                                </span>
                            </td>
                            <td rowspan="${numItems}" class="col-actions">
                                <button class="btn btn-secondary-icon btn-edit-row open-edit-btn" data-doc-no="${inv.doc_no}" title="Edit document details">
                                    <i class="fa-solid fa-pen"></i>
                                </button>
                                <button class="btn btn-secondary-icon btn-delete-row" data-doc-no="${inv.doc_no}" title="Delete document" style="color: var(--danger)">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </td>
                        `;
                    }
                    
                    rowHtml += '</tr>';
                    finalHtml += rowHtml;
                }
            } else {
                // Invoice: Keep standard single-row layout
                const cellHtmlList = [
                    `<td class="col-sno">${index + 1}</td>`,
                    `<td class="col-invoice">${inv.doc_no || ''}</td>`
                ];
                cellHtmlList.push(`<td>${inv.doc_date || ''}</td>`);
                cellHtmlList.push(`<td>${inv.challan_no || ''}</td>`);
                cellHtmlList.push(`<td>${inv.bill_to || ''}</td>`);
                cellHtmlList.push(`<td>${inv.po_wo_no || ''}</td>`);
                cellHtmlList.push(`<td style="text-align: left; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${inv.item_description || ''}">${inv.item_description || ''}</td>`);
                cellHtmlList.push(`<td class="col-amount">${parseFloat(inv.amount || 0).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>`);
                cellHtmlList.push(`<td>${inv.eway_bill || ''}</td>`);
                cellHtmlList.push(`<td>${inv.eway_bill_no || ''}</td>`);
                cellHtmlList.push(`<td>${inv.asn_no || ''}</td>`);
                cellHtmlList.push(`<td>${inv.mode_of_transp || ''}</td>`);
                cellHtmlList.push(`<td>${inv.dock_code || ''}</td>`);
                cellHtmlList.push(`<td>${inv.delivery_date || ''}</td>`);
                cellHtmlList.push(`<td>${inv.delivery_site || ''}</td>`);
                cellHtmlList.push(`<td>${inv.mrn_status || 'PENDING'}</td>`);
                cellHtmlList.push(`<td>${inv.mrn_date || ''}</td>`);
                cellHtmlList.push(`<td>${inv.mrn_no || ''}</td>`);
                
                cellHtmlList.push(`
                    <td>
                        <span class="editable-cell open-edit-btn" data-doc-no="${inv.doc_no}">
                            ${inv.remarks || '-'}
                        </span>
                    </td>
                    <td class="col-actions">
                        <button class="btn btn-secondary-icon btn-edit-row open-edit-btn" data-doc-no="${inv.doc_no}" title="Edit document details">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn btn-secondary-icon btn-delete-row" data-doc-no="${inv.doc_no}" title="Delete document" style="color: var(--danger)">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                `);
                
                finalHtml += `<tr>${cellHtmlList.join("")}</tr>`;
            }
        });
        
        ledgerBody.innerHTML = finalHtml;

        document.querySelectorAll(".open-edit-btn").forEach(el => {
            el.addEventListener("click", () => {
                const docNo = el.getAttribute("data-doc-no");
                openEditModal(docNo);
            });
        });

        document.querySelectorAll(".btn-delete-row").forEach(btn => {
            btn.addEventListener("click", () => {
                const docNo = btn.getAttribute("data-doc-no");
                if (confirm(`Are you sure you want to delete this document ${docNo}? This will rewrite Excel and Pending files.`)) {
                    deleteDocument(docNo);
                }
            });
        });
    }

    function deleteDocument(docNo) {
        const comp = state.activeCompany;
        const docType = ledgerModuleFilter.value;
        
        fetch(`/api/invoices/${encodeURIComponent(comp)}/${encodeURIComponent(docType)}/${encodeURIComponent(docNo)}`, { 
            method: 'DELETE',
            headers: getAuthHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                showToast(`Document ${docNo} deleted successfully.`);
                fetchLedger();
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            console.error("Error deleting document:", err);
            showToast("Failed to delete document.", "danger");
        });
    }

    ledgerSearch.addEventListener("keyup", () => renderLedgerTable(state.invoices, ledgerModuleFilter.value));
    ledgerMrnFilter.addEventListener("change", () => renderLedgerTable(state.invoices, ledgerModuleFilter.value));
    refreshLedgerBtn.addEventListener("click", () => fetchLedger());

    // --- UPLOAD & INGESTION LOGIC ---
    
    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
        }, false);
    });

    dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) handleFileUpload(files[0]);
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) handleFileUpload(fileInput.files[0]);
    });

    function handleFileUpload(file) {
        uploadReview.style.display = "none";
        state.currentUploadedData = null;
        
        statusFilename.innerText = file.name;
        uploadStatus.style.display = "block";
        dropzone.style.display = "none";
        
        statusProgressFill.style.width = "10%";
        statusMessage.innerText = "Uploading document to server...";

        const company = state.activeCompany; 
        const docType = uploadDocType.value;

        const formData = new FormData();
        formData.append("file", file);
        formData.append("company", company);
        formData.append("doc_type", docType);

        let progress = 10;
        const interval = setInterval(() => {
            if (progress < 85) {
                progress += Math.floor(Math.random() * 10) + 2;
                statusProgressFill.style.width = `${progress}%`;
                
                if (progress > 35 && progress < 65) {
                    statusMessage.innerText = "Extracting OCR text layouts via Azure AI Document Intelligence...";
                } else if (progress >= 65) {
                    statusMessage.innerText = "Parsing document fields and comparing duplicates...";
                }
            }
        }, 800);

        fetch("/api/upload", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${getAuthToken()}`
            },
            body: formData
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            clearInterval(interval);
            statusProgressFill.style.width = "100%";
            
            if (data.status === "success") {
                showToast("Document analyzed successfully!");
                uploadStatus.style.display = "none";
                state.currentUploadedData = data.data;
                showReviewPanel(data.data, docType);
            } else if (data.status === "duplicate") {
                showToast("Document number already exists!", "warning");
                uploadStatus.style.display = "none";
                openDuplicateModal(data.new_data, data.existing_data, docType);
            } else {
                showToast(data.message, "danger");
                uploadStatus.style.display = "none";
                dropzone.style.display = "flex";
            }
        })
        .catch(err => {
            clearInterval(interval);
            console.error("Upload error:", err);
            showToast("Server error during data extraction.", "danger");
            uploadStatus.style.display = "none";
            dropzone.style.display = "flex";
        });
    }

    const fieldLabelsInvoice = {
        doc_no: "Invoice No",
        doc_date: "Invoice Date",
        challan_no: "Challan No",
        bill_to: "Bill To",
        po_wo_no: "PO/WO No",
        item_description: "Item Description",
        amount: "Invoice Amt (₹)",
        eway_bill: "Eway Bill",
        eway_bill_no: "E-way Bill No.",
        asn_no: "ASN No",
        mode_of_transp: "Mode of Transp",
        dock_code: "Dock Code",
        delivery_date: "Delivery Date",
        delivery_site: "Delivery Site"
    };

    const fieldLabelsChallan = {
        doc_no: "Delivery Challan No",
        item_description: "Item Description",
        deliver_qty: "Deliver Qty",
        uom: "UOM",
        unit_price: "Unit Price",
        delivery_date: "Delivery Date",
        delivery_site: "Delivery Location",
        po_status: "PO Status",
        po_wo_no: "PO Number",
        po_qty: "PO Qty",
        invoice_no: "Invoice Number"
    };

    function showReviewPanel(docData, docType) {
        reviewFieldsContainer.innerHTML = "";
        const labelsMap = docType === "Challan" ? fieldLabelsChallan : fieldLabelsInvoice;
        
        for (const [key, label] of Object.entries(labelsMap)) {
            const val = docData[key] !== null && docData[key] !== undefined ? docData[key] : "";
            
            if (["item_description", "deliver_qty", "uom", "unit_price", "po_qty"].includes(key)) {
                reviewFieldsContainer.innerHTML += `
                    <div class="form-group ${key === 'item_description' ? 'span-2' : ''}">
                        <label for="review-${key}">${label}</label>
                        <textarea id="review-${key}" rows="3" placeholder="Not found">${val}</textarea>
                    </div>
                `;
            } else {
                const isAmt = (key === "amount");
                const inputType = isAmt ? "number" : "text";
                const stepAttr = isAmt ? 'step="0.01"' : '';
                
                reviewFieldsContainer.innerHTML += `
                    <div class="form-group ${key === 'bill_to' ? 'span-2' : ''}">
                        <label for="review-${key}">${label}</label>
                        <input type="${inputType}" id="review-${key}" value="${val}" ${stepAttr} placeholder="Not found">
                    </div>
                `;
            }
        }
        
        uploadReview.style.display = "block";
    }

    cancelReviewBtn.addEventListener("click", () => {
        if (confirm("Discard uploaded file?")) {
            uploadReview.style.display = "none";
            dropzone.style.display = "flex";
            fileInput.value = "";
        }
    });

    saveReviewBtn.addEventListener("click", () => {
        const finalData = { ...state.currentUploadedData };
        const docType = finalData.doc_type;
        const labelsMap = docType === "Challan" ? fieldLabelsChallan : fieldLabelsInvoice;
        
        for (const key of Object.keys(labelsMap)) {
            const inputEl = document.getElementById(`review-${key}`);
            if (inputEl) {
                finalData[key] = key === "amount" ? parseFloat(inputEl.value) || 0.0 : inputEl.value;
            }
        }

        saveReviewBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        saveReviewBtn.disabled = true;

        fetch("/api/invoices/confirm-upload", {
            method: "POST",
            headers: getAuthHeaders(true),
            body: JSON.stringify({ action: "replace", data: finalData })
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            saveReviewBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Save & Lock Ledger';
            saveReviewBtn.disabled = false;
            
            if (data.status === "success" || data.status === "skipped") {
                showToast("Document recorded and synced to company workbook!");
                uploadReview.style.display = "none";
                dropzone.style.display = "flex";
                fileInput.value = "";
                
                state.activeCompany = finalData.company;
                state.activeDocType = finalData.doc_type;
                switchTab("invoices");
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            saveReviewBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Save & Lock Ledger';
            saveReviewBtn.disabled = false;
            console.error("Save review error:", err);
            showToast("Failed to save document details.", "danger");
        });
    });

    // --- DUPLICATE CONFLICT DIALOG ---
    
    function openDuplicateModal(newData, existingData, docType) {
        dupInvoiceNo.innerText = newData.doc_no;
        dupComparisonBody.innerHTML = "";
        
        const labelsMap = docType === "Challan" ? fieldLabelsChallan : fieldLabelsInvoice;
        
        for (const [key, label] of Object.entries(labelsMap)) {
            const oldVal = existingData[key] !== null && existingData[key] !== undefined ? existingData[key] : "-";
            const newVal = newData[key] !== null && newData[key] !== undefined ? newData[key] : "-";
            
            const isDifferent = String(oldVal).trim() !== String(newVal).trim();
            const rowClass = isDifferent ? "highlight" : "";
            
            dupComparisonBody.innerHTML += `
                <tr class="${rowClass}">
                    <td><strong>${label}</strong></td>
                    <td style="white-space: pre-line;">${key === 'amount' ? formatCurrency(oldVal) : oldVal}</td>
                    <td class="${rowClass}" style="white-space: pre-line;">${key === 'amount' ? formatCurrency(newVal) : newVal}</td>
                </tr>
            `;
        }

        state.currentUploadedData = newData;
        duplicateModal.style.display = "flex";
    }

    function closeDuplicateDialog() {
        duplicateModal.style.display = "none";
        dropzone.style.display = "flex";
        fileInput.value = "";
    }

    closeDupModal.addEventListener("click", closeDuplicateDialog);
    dupSkipBtn.addEventListener("click", () => {
        closeDuplicateDialog();
        showToast("Upload cancelled.", "warning");
    });

    dupReplaceBtn.addEventListener("click", () => {
        duplicateModal.style.display = "none";
        showReviewPanel(state.currentUploadedData, state.currentUploadedData.doc_type);
    });

    // --- EDIT MRN & FIELD EDIT DIALOG ---
    
    // --- EDIT MRN & FIELD EDIT DIALOG (FLATPICKR CALENDAR INTEGRATION) ---
    
    let mrnFlatpickr = null;
    const editMrnDateInput = document.getElementById("edit-mrn-date");
    const editMrnDateBtn = document.getElementById("edit-mrn-date-btn");

    if (editMrnDateInput && typeof flatpickr !== "undefined") {
        mrnFlatpickr = flatpickr(editMrnDateInput, {
            dateFormat: "d F Y",
            allowInput: true,
            theme: "dark",
            onReady: function(selectedDates, dateStr, instance) {
                if (editMrnDateBtn) {
                    editMrnDateBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        instance.toggle();
                    });
                }
            }
        });
    }
    
    function openEditModal(docNo) {
        const doc = state.invoices.find(d => String(d.doc_no || '').trim().toLowerCase() === String(docNo || '').trim().toLowerCase());
        if (!doc) return;
        
        editInvoiceNo.value = doc.doc_no;
        editMrnStatus.value = doc.mrn_status || "PENDING";
        editMrnDate.value = doc.mrn_date || "";
        if (mrnFlatpickr) {
            mrnFlatpickr.setDate(doc.mrn_date || "", true);
        }
        editMrnNo.value = doc.mrn_no || "";
        editRemarks.value = doc.remarks || "";

        // BUG FIX: Store the actual company and doc_type from the document so the submit
        // handler always uses the exact document company regardless of the dashboard dropdown.
        editInvoiceNo.setAttribute("data-company", doc.company || state.activeCompany);
        editInvoiceNo.setAttribute("data-doc-type", doc.doc_type || "Invoice");
        
        if (doc.doc_type === "Challan") {
            editMrnSection.style.display = "none";
            editChallanFields.style.display = "block";
            editItemDescription.value = doc.item_description || "";
            editDeliverQty.value = doc.deliver_qty || "";
            editUom.value = doc.uom || "";
            editUnitPrice.value = doc.unit_price || "";
            editPoQty.value = doc.po_qty || "";
            editPoStatus.value = doc.po_status || "Open";
            editInvoiceNoVal.value = doc.invoice_no || "";
            editInvoiceItemDescGroup.style.display = "none";
            document.getElementById("edit-eway-bill-group").style.display = "none";
            if (document.getElementById("edit-asn-no-group")) document.getElementById("edit-asn-no-group").style.display = "none";

            // Populate Item-wise PO Status List
            const descs = (doc.item_description || "").split('\n');
            const qtys = (doc.deliver_qty || "").split('\n');
            const uoms = (doc.uom || "").split('\n');
            const prices = (doc.unit_price || "").split('\n');
            const po_qtys = (doc.po_qty || "").split('\n');
            const po_stats = (doc.po_status || "").split('\n');

            const numItems = Math.max(descs.length, qtys.length, uoms.length, prices.length, po_qtys.length, po_stats.length, 1);
            
            const container = document.getElementById("edit-challan-items-container");
            if (container) {
                container.innerHTML = "";

                const getItemStatus = (i) => {
                    let st = (po_stats[i] || '').trim();
                    if (!st || st.toUpperCase() === 'OPEN') return 'Open';
                    if (st.toUpperCase() === 'CLOSE' || st.toUpperCase() === 'CLOSED') return 'Close';
                    if (st.toUpperCase() === 'WORK ORDER' || st.toUpperCase() === 'WORKORDER') return 'Work Order';
                    return 'Open';
                };

                for (let i = 0; i < numItems; i++) {
                    const desc = descs[i] || `Item ${i+1}`;
                    const delQty = qtys[i] || '';
                    const uom = uoms[i] || '';
                    const poQty = po_qtys[i] || '';
                    const curSt = getItemStatus(i);

                    const itemDiv = document.createElement("div");
                    itemDiv.className = "item-status-card";
                    itemDiv.style.cssText = "background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px;";
                    itemDiv.innerHTML = `
                        <div style="flex-grow: 1;">
                            <div style="font-weight: 600; font-size: 13px; color: var(--text-primary);">
                                <strong>Item ${i+1}:</strong> ${desc}
                            </div>
                            <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                                Deliver Qty: ${delQty} ${uom} | PO Qty: ${poQty}
                            </div>
                        </div>
                        <div style="width: 140px; flex-shrink: 0;">
                            <label style="font-size: 10px; font-weight: 600; display: block; margin-bottom: 2px; color: var(--text-secondary);">Item PO Status</label>
                            <select class="item-po-status-select form-control" data-index="${i}" style="width: 100%; padding: 6px 10px; border-radius: 6px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); color: var(--text-primary); font-weight: 600; font-size: 12px;">
                                <option value="Open" ${curSt === 'Open' ? 'selected' : ''}>Open</option>
                                <option value="Close" ${curSt === 'Close' ? 'selected' : ''}>Close</option>
                                <option value="Work Order" ${curSt === 'Work Order' ? 'selected' : ''}>Work Order</option>
                            </select>
                        </div>
                    `;
                    container.appendChild(itemDiv);
                }

                // Sync initial Overall PO Status dropdown & badge
                const overallSelect = document.getElementById("edit-overall-po-status");
                const overallBadge = document.getElementById("overall-po-status-badge");
                
                const updateOverallBadge = (statusVal) => {
                    if (!overallBadge) return;
                    overallBadge.innerText = statusVal;
                    if (statusVal === 'Close') {
                        overallBadge.className = 'count-badge badge-success';
                    } else if (statusVal === 'Work Order') {
                        overallBadge.className = 'count-badge badge-info';
                    } else {
                        overallBadge.className = 'count-badge badge-warning';
                    }
                };

                const initialOverall = calculateOverallPoStatusFromDoc(doc);
                if (overallSelect) overallSelect.value = initialOverall;
                updateOverallBadge(initialOverall);

                // Helper to sync all item select dropdowns back to hidden editPoStatus textarea & update overall dropdown
                const syncItemsToHiddenTextarea = () => {
                    const itemSelects = container.querySelectorAll(".item-po-status-select");
                    const statuses = Array.from(itemSelects).map(sel => sel.value);
                    editPoStatus.value = statuses.join("\n");
                    
                    const newOverall = calculateOverallPoStatusFromList(statuses);
                    if (overallSelect) overallSelect.value = newOverall;
                    updateOverallBadge(newOverall);
                };

                // Requirement 2 & 4: Event listener for individual item dropdown changes
                container.querySelectorAll(".item-po-status-select").forEach(sel => {
                    sel.addEventListener("change", syncItemsToHiddenTextarea);
                });

                // Requirement 3 & 4: Event listener for Overall PO Status dropdown change
                if (overallSelect) {
                    overallSelect.onchange = () => {
                        const targetVal = overallSelect.value;
                        container.querySelectorAll(".item-po-status-select").forEach(sel => {
                            sel.value = targetVal;
                        });
                        syncItemsToHiddenTextarea();
                    };
                }
            }
        } else {
            editMrnSection.style.display = "grid";
            editChallanFields.style.display = "none";
            editInvoiceItemDescGroup.style.display = "block";
            editInvoiceItemDescription.value = doc.item_description || "";
            document.getElementById("edit-eway-bill-group").style.display = "block";
            document.getElementById("edit-eway-bill").value = doc.eway_bill || "";
            if (document.getElementById("edit-asn-no-group")) {
                document.getElementById("edit-asn-no-group").style.display = "block";
                document.getElementById("edit-asn-no").value = doc.asn_no || "";
            }
        }
        
        editModal.style.display = "flex";
    }

    function closeEditDialog() {
        editModal.style.display = "none";
    }

    closeEditModal.addEventListener("click", closeEditDialog);
    editCancelBtn.addEventListener("click", closeEditDialog);

    editForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const docNo = editInvoiceNo.value;
        const comp = editInvoiceNo.getAttribute("data-company") || state.activeCompany;
        const docType = editInvoiceNo.getAttribute("data-doc-type") || ledgerModuleFilter.value;
        
        const updatedData = {
            remarks: editRemarks.value
        };

        if (docType === "Invoice") {
            updatedData.mrn_status = editMrnStatus.value;
            updatedData.mrn_date = editMrnDate.value;
            updatedData.mrn_no = editMrnNo.value;
            updatedData.item_description = editInvoiceItemDescription.value;
            updatedData.eway_bill = document.getElementById("edit-eway-bill").value;
            if (document.getElementById("edit-asn-no")) {
                updatedData.asn_no = document.getElementById("edit-asn-no").value.trim();
            }

            // Optimistic local update
            const targetInv = state.invoices.find(inv => String(inv.doc_no || '').trim().toLowerCase() === String(docNo || '').trim().toLowerCase());
            if (targetInv) {
                targetInv.mrn_status = editMrnStatus.value;
                targetInv.mrn_date = editMrnDate.value;
                targetInv.mrn_no = editMrnNo.value;
                targetInv.remarks = editRemarks.value;
                if (updatedData.asn_no !== undefined) {
                    targetInv.asn_no = updatedData.asn_no;
                }
                if (updatedData.eway_bill) {
                    targetInv.eway_bill_no = updatedData.eway_bill;
                    targetInv.eway_bill = 'DONE';
                }
            }
            renderAlertLists();
        }

        if (docType === "Challan") {
            updatedData.item_description = editItemDescription.value;
            updatedData.deliver_qty = editDeliverQty.value;
            updatedData.uom = editUom.value;
            updatedData.unit_price = editUnitPrice.value;
            updatedData.po_qty = editPoQty.value;
            updatedData.po_status = editPoStatus.value;
            updatedData.invoice_no = editInvoiceNoVal.value;

            // Optimistic local update
            const targetInv = state.invoices.find(inv => String(inv.doc_no || '').trim().toLowerCase() === String(docNo || '').trim().toLowerCase());
            if (targetInv) {
                targetInv.po_status = editPoStatus.value;
            }
            renderAlertLists();
        }

        fetch(`/api/invoices/${encodeURIComponent(comp)}/${encodeURIComponent(docType)}/${encodeURIComponent(docNo)}`, {
            method: "PUT",
            headers: getAuthHeaders(true),
            body: JSON.stringify(updatedData)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                showToast("Document details updated successfully!");
                closeEditDialog();
                if (state.activeTab === "dashboard") {
                    fetchData();
                } else if (state.activeTab === "invoices") {
                    fetchLedger();
                }
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            console.error("Error saving edits:", err);
            showToast("Failed to save changes.", "danger");
        });
    });

    // --- SYSTEM SETTINGS ---
    
    function fetchSettings() {
        if (!getAuthToken()) {
            showLoginScreen();
            return;
        }

        fetch("/api/settings", {
            headers: getSettingsHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            state.settings = data;
            settingsAdminUsername.value = data.admin_username || "";
            settingsAdminPassword.value = "";
            document.getElementById("settings-confirm-password").value = "";
            document.getElementById("settings-lock-password").value = "";
            document.getElementById("settings-current-password").value = "";
            settingsAzureEndpoint.value = data.azure_endpoint || "";
            settingsAzureKey.value = data.azure_api_key_masked || "";
            settingsExcelDir.value = data.excel_storage_directory || "";
            settingsTeamsWebhook.value = data.teams_webhook_url || "";
            
            // Load Google Sheets fields
            settingsGsheetUrlSkAgro.value = data.gsheet_url_sk_agro || "";
            settingsGsheetSyncUrlSkAgro.value = data.gsheet_sync_url_sk_agro || "";
            settingsGsheetUrlSkElectricals.value = data.gsheet_url_sk_electricals || "";
            settingsGsheetSyncUrlSkElectricals.value = data.gsheet_sync_url_sk_electricals || "";
            settingsGsheetUrlTriotech.value = data.gsheet_url_triotech || "";
            settingsGsheetSyncUrlTriotech.value = data.gsheet_sync_url_triotech || "";
        })
        .catch(err => console.error("Error loading settings:", err));
    }

    saveSettingsBtn.addEventListener("click", () => {
        const admin_user = settingsAdminUsername.value.trim();
        const admin_pass = settingsAdminPassword.value.trim();
        const azure_endpoint = settingsAzureEndpoint.value.trim();
        const azure_key = settingsAzureKey.value.trim();
        const excel_dir = settingsExcelDir.value.trim();
        const teams_webhook = settingsTeamsWebhook.value.trim();
        
        // Google Sheets settings values
        const gsheet_url_sk_agro = settingsGsheetUrlSkAgro.value.trim();
        const gsheet_sync_url_sk_agro = settingsGsheetSyncUrlSkAgro.value.trim();
        const gsheet_url_sk_electricals = settingsGsheetUrlSkElectricals.value.trim();
        const gsheet_sync_url_sk_electricals = settingsGsheetSyncUrlSkElectricals.value.trim();
        const gsheet_url_triotech = settingsGsheetUrlTriotech.value.trim();
        const gsheet_sync_url_triotech = settingsGsheetSyncUrlTriotech.value.trim();
        
        const settingsConfirmPassword = document.getElementById("settings-confirm-password");
        const settingsLockPassword = document.getElementById("settings-lock-password");
        const settingsCurrentPassword = document.getElementById("settings-current-password");

        const confirm_pass = settingsConfirmPassword.value.trim();
        const lock_pass = settingsLockPassword.value.trim();
        const current_pass = settingsCurrentPassword.value.trim();
        
        const payload = {};
        
        // Only trigger validation if username/password/settings-lock actually changed
        const usernameChanged = (admin_user && admin_user !== (state.settings.admin_username || "admin"));
        const passwordChanged = (admin_pass !== "");
        const passwordLockChanged = (lock_pass !== "");
        
        if (usernameChanged || passwordChanged || passwordLockChanged) {
            if (!current_pass) {
                showToast("Current password is required to change Access Control credentials.", "warning");
                return;
            }
            if (passwordChanged && admin_pass !== confirm_pass) {
                showToast("New Password and Confirm Password do not match.", "warning");
                return;
            }
            if (usernameChanged) payload.admin_username = admin_user;
            if (passwordChanged) payload.admin_password = admin_pass;
            if (passwordLockChanged) payload.settings_lock_password = lock_pass;
            payload.current_password = current_pass;
        }
        
        if (azure_endpoint !== undefined) payload.azure_endpoint = azure_endpoint;
        if (azure_key) payload.azure_api_key = azure_key;
        if (excel_dir !== undefined) payload.excel_storage_directory = excel_dir;
        if (teams_webhook !== undefined) payload.teams_webhook_url = teams_webhook;

        // Save Google Sheets values to payload
        if (gsheet_url_sk_agro !== undefined) payload.gsheet_url_sk_agro = gsheet_url_sk_agro;
        if (gsheet_sync_url_sk_agro !== undefined) payload.gsheet_sync_url_sk_agro = gsheet_sync_url_sk_agro;
        if (gsheet_url_sk_electricals !== undefined) payload.gsheet_url_sk_electricals = gsheet_url_sk_electricals;
        if (gsheet_sync_url_sk_electricals !== undefined) payload.gsheet_sync_url_sk_electricals = gsheet_sync_url_sk_electricals;
        if (gsheet_url_triotech !== undefined) payload.gsheet_url_triotech = gsheet_url_triotech;
        if (gsheet_sync_url_triotech !== undefined) payload.gsheet_sync_url_triotech = gsheet_sync_url_triotech;

        fetch("/api/settings", {
            method: "POST",
            headers: getSettingsHeaders(true),
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (res.status === 400) {
                return res.json().then(data => {
                    showToast(data.message, "danger");
                    throw new Error(data.message);
                });
            }
            return checkAuthResponse(res);
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                showToast("System configurations saved successfully!");
                
                // If admin password was changed, update the client's token
                if (admin_pass) {
                    localStorage.setItem("auth_token", admin_pass);
                }
                
                // If settings lock password was changed, update state
                if (lock_pass) {
                    state.settingsPassword = lock_pass;
                }
                
                fetchSettings();
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            console.error("Save settings error:", err);
        });
    });

    testTeamsBtn.addEventListener("click", () => {
        testTeamsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending Test...';
        testTeamsBtn.disabled = true;

        fetch("/api/settings/test-teams", { 
            method: "POST",
            headers: getSettingsHeaders(false)
        })
        .then(checkAuthResponse)
        .then(res => res.json())
        .then(data => {
            testTeamsBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Send Test Notification';
            testTeamsBtn.disabled = false;
            
            if (data.status === "success") {
                showToast("Test notification sent successfully to MS Teams!");
            } else {
                showToast(data.message, "danger");
            }
        })
        .catch(err => {
            testTeamsBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Send Test Notification';
            testTeamsBtn.disabled = false;
            console.error("Teams test error:", err);
            showToast("Failed to send Teams test.", "danger");
        });
    });

    // Google Sheets Script and Instructions Modal Events
    const GOOGLE_APPS_SCRIPT_CODE = `// Google Sheets Collaboration Script for InvoSync
// Paste this in extensions > Apps Script editor in your spreadsheet.

function doGet(e) {
  var action = e.parameter.action;
  if (action === "read") {
    return ContentService.createTextOutput(JSON.stringify(readSheetData()))
      .setMimeType(ContentService.MimeType.JSON);
  }
  var sheetUrl = SpreadsheetApp.getActiveSpreadsheet().getUrl();
  return HtmlService.createHtmlOutput("<script>window.top.location.href='" + sheetUrl + "';</script>Redirecting to Google Sheet...");
}

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    var action = payload.action;
    if (action === "write") {
      var invoices = payload.invoices || [];
      var challans = payload.challans || [];
      var pending = payload.pending || [];
      writeSheetData("Invoices", invoices);
      writeSheetData("Delivery Challans", challans);
      writeSheetData("Pending MRNs", pending);
      return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "Sheets updated successfully" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function readSheetData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var data = { invoices: [], challans: [] };
  var invSheet = ss.getSheetByName("Invoices");
  if (invSheet) data.invoices = getRowsData(invSheet);
  var chalSheet = ss.getSheetByName("Delivery Challans");
  if (chalSheet) data.challans = getRowsData(chalSheet);
  return data;
}

function getRowsData(sheet) {
  var rows = [];
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2) return rows;
  
  // Determine sheet type to map generic "Column X" headers
  var sheetName = sheet.getName();
  var expectedCols = [];
  if (sheetName === "Invoices") {
    expectedCols = [
      'S.No', 'Invoice No', 'Invoice Date', 'Challan No', 'Bill To',
      'PO/WO No', 'Item Description', 'Invoice Amt', 'Eway Bill', 'E way Bill no', 'ASN No', 'Mode of Transp',
      'Dock Code', 'Delivery Date', 'Delivery Site', 'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
    ];
  } else if (sheetName === "Delivery Challans") {
    expectedCols = [
      'S.No', 'Delivery Challan No', 'Item Description', 'Deliver Qty', 'UOM',
      'Unit Price', 'Delivery Date', 'Delivery Location', 'PO Status', 'PO Number',
      'PO Qty', 'Difference Between Delivery & PO Qty', 'Invoice Number', 
      'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
    ];
  }
  
  // Find the header row dynamically
  var headerRowIndex = 1;
  var headers = [];
  for (var r = 1; r <= Math.min(10, lastRow); r++) {
    var rowValues = sheet.getRange(r, 1, 1, lastCol).getValues()[0];
    var hasInvoiceNo = rowValues.some(function(val) {
      var s = String(val).trim().toLowerCase();
      return s === "invoice no" || s === "delivery challan no" || s === "invoice number" || s === "s.no";
    });
    if (hasInvoiceNo) {
      headerRowIndex = r;
      headers = rowValues;
      break;
    }
  }
  
  if (headers.length === 0) {
    headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    headerRowIndex = 1;
  }
  
  var startRow = headerRowIndex + 1;
  if (lastRow < startRow) return rows;
  
  var values = sheet.getRange(startRow, 1, lastRow - startRow + 1, lastCol).getValues();
  for (var i = 0; i < values.length; i++) {
    var row = {};
    var hasData = false;
    for (var j = 0; j < headers.length; j++) {
      var rawHeader = String(headers[j]).trim();
      
      // If the header starts with "Column" or is empty, map by index
      var header = rawHeader;
      if (rawHeader.toLowerCase().indexOf("column") === 0 || !rawHeader) {
        if (j < expectedCols.length) {
          header = expectedCols[j];
        }
      }
      
      if (header) {
        var cellVal = values[i][j];
        row[header] = cellVal;
        if (cellVal !== "" && cellVal !== null && cellVal !== undefined) {
          hasData = true;
        }
      }
    }
    if (hasData) {
      rows.push(row);
    }
  }
  return rows;
}

function writeSheetData(sheetName, dataList) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);
  var cols = [];
  if (sheetName === "Invoices") {
    cols = [
      'S.No', 'Invoice No', 'Invoice Date', 'Challan No', 'Bill To',
      'PO/WO No', 'Item Description', 'Invoice Amt', 'Eway Bill', 'E way Bill no', 'ASN No', 'Mode of Transp',
      'Dock Code', 'Delivery Date', 'Delivery Site', 'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
    ];
  } else if (sheetName === "Delivery Challans") {
    cols = [
      'S.No', 'Delivery Challan No', 'Item Description', 'Deliver Qty', 'UOM',
      'Unit Price', 'Delivery Date', 'Delivery Location', 'PO Status', 'PO Number',
      'PO Qty', 'Difference Between Delivery & PO Qty', 'Invoice Number', 
      'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
    ];
  } else if (sheetName === "Pending MRNs") {
    cols = [
      'S.No', 'Invoice No', 'Invoice Date', 'Challan No', 'Bill To',
      'PO/WO No', 'Item Description', 'Invoice Amt', 'Eway Bill', 'E way Bill no', 'ASN No', 'Mode of Transp',
      'Dock Code', 'Delivery Date', 'Delivery Site', 'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
    ];
  }
  if (!sheet) sheet = ss.insertSheet(sheetName);
  sheet.clear();
  
  // Clear any existing data validation rules on the entire sheet to prevent old or misplaced validations
  // (like a validation rule stuck on a column that was moved or rearranged) from causing sync errors.
  try {
    sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).clearDataValidations();
  } catch (e) {
    // Fallback if sheet is empty or has no range
  }
  
  // Set headers directly on row 1 to prevent Google Sheets Tables from resetting
  // column headers to default values (like "Column 1", "Column 2") which happens when using appendRow.
  sheet.getRange(1, 1, 1, cols.length).setValues([cols]);
  
  if (dataList.length === 0) return;
  var rowsToWrite = [];
  for (var idx = 0; idx < dataList.length; idx++) {
    var doc = dataList[idx];
    var row = [];
    for (var c = 0; c < cols.length; c++) {
      row.push(doc[cols[c]] !== undefined && doc[cols[c]] !== null ? doc[cols[c]] : "");
    }
    rowsToWrite.push(row);
  }
  sheet.getRange(2, 1, rowsToWrite.length, cols.length).setValues(rowsToWrite);
  sheet.getRange(2, 1, rowsToWrite.length, cols.length).setWrap(true).setVerticalAlignment("top");
  sheet.getRange(1, 1, 1, cols.length).setFontWeight("bold").setBackground("#f3f3f3");
  
  // Re-apply correct validation rules programmatically to the correct columns
  try {
    var numRows = rowsToWrite.length;
    if (sheetName === "Delivery Challans") {
      // PO Status on Column 9 (Col I)
      var poRule = SpreadsheetApp.newDataValidation().requireValueInList(['Open', 'Closed'], true).build();
      sheet.getRange(2, 9, numRows, 1).setDataValidation(poRule);
      // MRN Status on Column 14 (Col N)
      var mrnRule = SpreadsheetApp.newDataValidation().requireValueInList(['PENDING', 'DONE'], true).build();
      sheet.getRange(2, 14, numRows, 1).setDataValidation(mrnRule);
    } else if (sheetName === "Invoices" || sheetName === "Pending MRNs") {
      // Eway Bill on Column 9 (Col I)
      var ewayRule = SpreadsheetApp.newDataValidation().requireValueInList(['PENDING', 'DONE', 'N/A'], true).build();
      sheet.getRange(2, 9, numRows, 1).setDataValidation(ewayRule);
      // MRN Status on Column 16 (Col P)
      var mrnRule = SpreadsheetApp.newDataValidation().requireValueInList(['PENDING', 'DONE'], true).build();
      sheet.getRange(2, 16, numRows, 1).setDataValidation(mrnRule);
    }
  } catch (vErr) {
    // Ignore validation application errors if range bounds are incorrect
  }
}`;

    viewGsheetInstructionsBtn.addEventListener("click", () => {
        gsheetScriptCode.value = GOOGLE_APPS_SCRIPT_CODE;
        gsheetInstructionsModal.style.display = "flex";
    });

    const closeGsheetInstructions = () => {
        gsheetInstructionsModal.style.display = "none";
    };

    closeGsheetModal.addEventListener("click", closeGsheetInstructions);
    closeGsheetInstructionsBtn.addEventListener("click", closeGsheetInstructions);

    copyGsheetCodeBtn.addEventListener("click", () => {
        gsheetScriptCode.select();
        document.execCommand("copy");
        showToast("Google Apps Script code copied to clipboard!");
    });

    // --- SETTINGS LOCK AUTH MODAL ---
    const settingsAuthModal = document.getElementById("settings-auth-modal");
    const settingsAuthForm = document.getElementById("settings-auth-form");
    const settingsAuthPassword = document.getElementById("settings-auth-password");
    const settingsAuthCancelBtn = document.getElementById("settings-auth-cancel-btn");
    const closeSettingsAuthModal = document.getElementById("close-settings-auth-modal");

    function openSettingsAuthModal() {
        settingsAuthPassword.value = "";
        settingsAuthModal.style.display = "flex";
        settingsAuthPassword.focus();
    }

    function closeSettingsAuthModalWindow() {
        settingsAuthModal.style.display = "none";
    }

    closeSettingsAuthModal.addEventListener("click", closeSettingsAuthModalWindow);
    settingsAuthCancelBtn.addEventListener("click", closeSettingsAuthModalWindow);

    if (settingsAuthPassword) {
        settingsAuthPassword.addEventListener("input", () => {
            settingsAuthPassword.classList.remove("input-error");
            const settingsAuthErrorAlert = document.getElementById("settings-auth-error-alert");
            if (settingsAuthErrorAlert) settingsAuthErrorAlert.style.display = "none";
        });
    }

    settingsAuthForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const pwd = settingsAuthPassword.value.trim();
        const settingsAuthErrorAlert = document.getElementById("settings-auth-error-alert");
        const settingsAuthErrorText = document.getElementById("settings-auth-error-text");
        const modalBox = settingsAuthModal.querySelector(".modal-box");
        
        if (settingsAuthErrorAlert) settingsAuthErrorAlert.style.display = "none";
        settingsAuthPassword.classList.remove("input-error");
        if (modalBox) modalBox.classList.remove("shake");
        
        fetch("/api/settings", {
            headers: {
                "Authorization": `Bearer ${pwd}`
            }
        })
        .then(res => {
            if (res.status === 401) {
                const errMsg = "Incorrect Settings Lock password.";
                if (settingsAuthErrorAlert && settingsAuthErrorText) {
                    settingsAuthErrorText.textContent = errMsg;
                    settingsAuthErrorAlert.style.display = "flex";
                }
                settingsAuthPassword.classList.add("input-error");
                if (modalBox) {
                    void modalBox.offsetWidth;
                    modalBox.classList.add("shake");
                }
                settingsAuthPassword.focus();
                settingsAuthPassword.select();
                showToast(errMsg, "danger");
                throw new Error("Unauthorized settings lock password");
            }
            if (!res.ok) {
                showToast("Server error during validation.", "danger");
                throw new Error("Server error");
            }
            return res.json();
        })
        .then(data => {
            state.settingsPassword = pwd;
            closeSettingsAuthModalWindow();
            showToast("Settings unlocked successfully!");
            switchTab("settings");
        })
        .catch(err => {
            console.error("Settings lock auth error:", err);
        });
    });

    // Accordion dropdown toggles for Critical Action Center
    document.querySelectorAll(".accordion-header").forEach(header => {
        header.addEventListener("click", () => {
            const targetId = header.getAttribute("data-target");
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                header.classList.toggle("collapsed");
                targetEl.classList.toggle("collapsed");
            }
        });
    });

    // Initial page load check
    if (getAuthToken()) {
        hideLoginScreen();
        switchTab("dashboard");
    } else {
        showLoginScreen();
    }
});
