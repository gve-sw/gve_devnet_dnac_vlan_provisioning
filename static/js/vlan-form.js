var table_rows = 1;

/*
   DRAG & DROP COMPONENTS
*/
function onDragStart(event) {
    event
        .dataTransfer
        .setData('text/plain', event.target.id);

    event
        .currentTarget
        .style
}

function onDragOver(event) {
    event.preventDefault();
}

function onDrop(event, element) {
    const id = event
        .dataTransfer
        .getData('text');
    element.appendChild(document.getElementById(id));
    event
        .dataTransfer
        .clearData();
}

function onDropItem(event) {
    const id = event
        .dataTransfer
        .getData('text');
    const draggableElement = document.getElementById(id);
    const dropzone = event.currentTarget;
    dropzone.appendChild(draggableElement);
    event
        .dataTransfer
        .clearData();
}

/*
   VLAN FORM SUBMISSION
*/
var vlanform = document.getElementById("vlan-form");
vlanform.addEventListener("submit", (e) => {
    // Manual form submit so we can loop over table rows
    e.preventDefault();

    var vlan_table = document.getElementById("table-body");
    var form_data = {};

    for (var i = 0, row; row = vlan_table.rows[i]; i++) {
        // Collect entries from each row
        var row_data = {};
        var vlan_id = row.querySelector("input[id='vlan-id']");
        row_data["vlan_id"] = vlan_id.value;
        var vlan_name = row.querySelector("input[id='vlan-name']");
        row_data["vlan_name"] = vlan_name.value;
        // Validate VLAN name
        if (/^[a-zA-Z0-9\-\_]+$/.test(row_data["vlan_name"]) == false) {
            alert("VLAN name can only contain alphanumeric characters, dashes, or underscores.")
            return
        }
        var ports = row.querySelector("div[id='tagged-ports']");
        row_data["ports"] = ports.innerText;
        // Check for empty port list & return error
        if (row_data["ports"].length == 0) {
            alert("Cannot apply VLAN with no ports assigned.")
            return
        }
        // Append to form data dict
        form_data[i] = row_data;
    }

    // Disable submit button & pop loading wheel
    button = document.getElementById("submit");
    button.disabled = true;

    submit_section = document.getElementById("submit-section");
    loader_div = document.createElement("div");
    loader_div.setAttribute("class", "loader loader--small");
    wrapper_div = document.createElement("div");
    wrapper_div.setAttribute("class", "wrapper");
    loader = document.createElement("div");
    loader.setAttribute("class", "wheel");

    submit_section.appendChild(loader_div);
    loader_div.appendChild(wrapper_div);
    wrapper_div.appendChild(loader);

    // Send request to Flask & redirect to /status on completion
    const request = new XMLHttpRequest();
    request.onload = function () {
        window.location.replace("/status");

    }
    request.open("POST", "/vlan-provision", true);
    request.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    request.send(JSON.stringify(form_data));
});


/*
   VLAN FORM - ADD/REMOVE ROWS
*/
function add_vlan() {
    var table = document.getElementById("table-body");

    // Create new table row
    table_rows += 1;
    var row = document.createElement("tr");
    row.setAttribute("id", table_rows)
    table.appendChild(row);

    // Create VLAN ID Field
    var vlan_id_cell = document.createElement("td");
    vlan_id_cell.setAttribute("style", "text-align: center;")
    var vlan_id_div = document.createElement("div");
    vlan_id_div.setAttribute("class", "form-group form-group--inline form-group__text")
    var vlan_id_subdiv = document.createElement("div");
    vlan_id_subdiv.setAttribute("class", "form-group__text")

    var vlan_id_input = document.createElement("input");
    vlan_id_input.setAttribute("type", "number");
    vlan_id_input.setAttribute("style", "min-width: 100px");
    vlan_id_input.setAttribute("min", "1");
    vlan_id_input.setAttribute("max", "4096");
    vlan_id_input.setAttribute("id", "vlan-id");
    vlan_id_input.setAttribute("name", "vlan-id");
    vlan_id_input.setAttribute("required", "");

    row.appendChild(vlan_id_cell);
    vlan_id_cell.appendChild(vlan_id_div);
    vlan_id_div.appendChild(vlan_id_subdiv);
    vlan_id_subdiv.appendChild(vlan_id_input);

    // Create VLAN Name Field
    var vlan_name_cell = document.createElement("td");
    vlan_name_cell.setAttribute("style", "text-align: center;")
    var vlan_name_div = document.createElement("div");
    vlan_name_div.setAttribute("class", "form-group form-group--inline form-group__text")
    var vlan_name_subdiv = document.createElement("div");
    vlan_name_subdiv.setAttribute("class", "form-group__text")

    var vlan_name_input = document.createElement("input");
    vlan_name_input.setAttribute("type", "text");
    vlan_name_input.setAttribute("style", "min-width: 200px");
    vlan_name_input.setAttribute("id", "vlan-name");
    vlan_name_input.setAttribute("name", "vlan-name");
    vlan_name_input.setAttribute("required", "");

    row.appendChild(vlan_name_cell);
    vlan_name_cell.appendChild(vlan_name_div);
    vlan_name_div.appendChild(vlan_name_subdiv);
    vlan_name_subdiv.appendChild(vlan_name_input);

    // Create drag & Drop
    var vlan_ports_cell = document.createElement("td");
    vlan_ports_cell.setAttribute("style", "text-align: center;")
    var vlan_ports_div = document.createElement("div");
    vlan_ports_div.setAttribute("class", "dropzone")

    vlan_ports_div.setAttribute("ondragover", "onDragOver(event);");
    vlan_ports_div.setAttribute("ondrop", "onDrop(event, this);");
    vlan_ports_div.setAttribute("id", "tagged-ports");
    vlan_ports_div.setAttribute("name", "tagged-ports");

    row.appendChild(vlan_ports_cell);
    vlan_ports_cell.appendChild(vlan_ports_div);

    // Create row remove button
    var remove_cell = document.createElement("td");
    var remove_button = document.createElement("button");
    remove_button.setAttribute("class", "btn btn--circle btn--small");
    remove_button.setAttribute("type", "other");
    remove_button.setAttribute("onclick", `remove_vlan(${table_rows})`);
    remove_button.setAttribute("class", "btn btn--circle btn--small");
    var button_icon = document.createElement("span")
    button_icon.setAttribute("class", "icon-remove");

    row.appendChild(remove_cell);
    remove_cell.appendChild(remove_button);
    remove_button.appendChild(button_icon);

}

function remove_vlan(row_id) {
    // Remove row by id
    var table = document.getElementById("table-body");
    var row = document.getElementById(row_id);
    ports = row.querySelector("div[id='tagged-ports']");

    // Check that ports are empty first
    if (ports.innerText != "") {
        alert("Please remove all ports from VLAN before deleting.")
        return
    }
    // Remove element
    table.removeChild(row);
}