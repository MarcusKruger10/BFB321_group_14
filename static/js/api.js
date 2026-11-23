// B3: shared helpers for calling the group's JSON API (B2) from the pages.
// Every API response is {"data": ...} on success or {"error": {...}} on failure.

async function apiRequest(method, url, body) {
    const options = { method: method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) options.body = JSON.stringify(body);
    const response = await fetch(url, options);
    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
        const error = json.error || {};
        let message = error.message || `Request failed (${response.status})`;
        if (error.details) {
            message += ": " + Object.entries(error.details)
                .map(([field, problem]) => `${field} ${problem}`).join(", ");
        }
        throw new Error(message);
    }
    return json.data;
}

// Show a Bootstrap message under the page title (green, yellow or red)
function showMessage(text, type = "success") {
    let area = document.getElementById("messages");
    if (!area) {
        area = document.createElement("div");
        area.id = "messages";
        document.querySelector(".app-intro").after(area);
    }
    const box = document.createElement("div");
    box.className = `alert alert-${type} alert-dismissible fade show`;
    box.setAttribute("role", "alert");
    box.textContent = text;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("data-bs-dismiss", "alert");
    close.setAttribute("aria-label", "Close");
    box.appendChild(close);
    area.appendChild(box);
}

function clearMessages() {
    const area = document.getElementById("messages");
    if (area) area.innerHTML = "";
}

// Add a new row to the top of a table and highlight it for 3 seconds
function addTableRow(tbody, cells) {
    const emptyRow = tbody.querySelector("td[colspan]");
    if (emptyRow) emptyRow.parentElement.remove();
    const row = document.createElement("tr");
    cells.forEach(value => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
    });
    tbody.prepend(row);
    row.classList.add("table-success");
    setTimeout(() => row.classList.remove("table-success"), 3000);
}

function productName(p) {
    return `${p.name} ${p.strength || ""}`.trim();
}

// Update a product's dropdown text with its new stock level and status
function updateProductOption(select, p) {
    const option = select.querySelector(`option[value="${p.product_id}"]`);
    if (option) option.textContent = `${productName(p)} (${p.stock_on_hand} in stock - ${p.reorder_status})`;
}

function nowText() {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}