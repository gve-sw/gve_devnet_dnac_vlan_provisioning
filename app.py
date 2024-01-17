""" Copyright (c) 2024 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. 
"""

# Import Section
import os
import re
import secrets
import string
import sys
from datetime import datetime
from time import sleep

import yaml
from dnacentersdk import api
from dnacentersdk.exceptions import ApiError
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session
from jinja2 import Environment, FileSystemLoader

from flask_session import Session

# Load environment variables
load_dotenv()
CUSTOMER_NAME = os.getenv("CUSTOMER_NAME", "Cisco Catalyst Center")
# App Mode enables single-credential or multiple-credential authentication to DNA Center.
# SINGLEAUTH mode means that the credentials used to log into the web app are also used to push templates to DNA Center.
# MULTIAUTH mode allows users with DNAC read-only API access to use this app by providing a separate API write credential
APP_MODE = os.getenv("APP_MODE", "SINGLEAUTH")
if APP_MODE == "MULTIAUTH":
    print("INFO: App running in multi-auth mode")
    DNAC_USER = os.getenv("DNAC_USER")
    DNAC_PASS = os.getenv("DNAC_PASS")
    if not DNAC_USER or not DNAC_PASS:
        print(
            "ERROR: If multiple authentication is enabled, "
            + "then DNA center credentials must be provided via "
            + "DNAC_USER and DNAC_PASS environment variables."
        )
        sys.exit(1)
else:
    print("INFO: App running in single-auth mode")


# Load target DNAC Servers from config YAML
with open("./dna-servers.yaml") as config:
    try:
        dnac_config = yaml.safe_load(config)
    except yaml.YAMLError as e:
        print(f"Error loading dna-servers.yaml: {e}")
        sys.exit(1)

# Load Jinja config templates
conf_templates = Environment(loader=FileSystemLoader("config_templates/"))

# Set up Flask App & Session handling
app = Flask(__name__)
app.secret_key = "".join(
    (secrets.choice(string.ascii_letters + string.digits) for i in range(16))
)
app.config["PERMANENT_SESSION_LIFETIME"] = 3540
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/", methods=["GET"])
def index():
    """
    Index

    If user is authenticated, redirect to device selection page.
    Otherwise, send to login page.
    """
    if not session.get("auth"):
        return redirect("/login")
    else:
        return redirect("/select-device")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login

    Collect user credentials & check ability to log into DNAC.
    """
    # Set up session data
    session["deploymentError"] = None
    session["deploymentStatus"] = None
    session["template_payload"] = None
    session["target_device"] = None

    # On GET, render login page:
    if request.method == "GET":
        # If already authenticated, redirect
        if session.get("auth"):
            return redirect("/select-device")
        return render_template(
            "login.html",
            dnac=dnac_config,
            customer_name=CUSTOMER_NAME,
        )

    # If login form submitted, attempt to log into DNAC
    if request.method == "POST":
        # Store server-side session data for future requests
        session["server"] = request.form.get("server")
        session["username"] = request.form.get("username")
        session["password"] = request.form.get("password")
        # Store user name to add author to DNAC templates
        session["author"] = request.form.get("username")

        # Generate DNAC server URL
        server_address = dnac_config["servers"][session["server"]]["address"]
        session["dnac_url"] = f"https://{server_address}/"

        # Attempt DNAC Login
        try:
            # Single auth mode, user's login credentials are used for all subsequent calls
            if APP_MODE == "SINGLEAUTH":
                dnac = getDNACSession()
            # Multi auth mode, user's login credentials only used for initial auth
            # Subsequent calls use admin-provided credentials
            elif APP_MODE == "MULTIAUTH":
                dnac = getDNACSession()
                session["username"] = DNAC_USER
                session["password"] = DNAC_PASS
        except Exception as e:
            # Return login page with error from DNAC
            errormessage = f"Failed to log in: \n {e}"
            session["auth"] = False
            return render_template(
                "login.html",
                dnac=dnac_config,
                error=errormessage,
                customer_name=CUSTOMER_NAME,
            )
        if dnac.access_token != "":
            # As long we verified we could authenticate once, mark session as authenticated
            # and send user to VLAN provisioning page
            session["auth"] = True
            return redirect("/select-device")
        else:
            # If for some reason we don't have an authentication token, return login page & error
            errormessage = "Invalid DNAC access token"
            session["auth"] = False
            return render_template(
                "login.html",
                dnac=dnac_config,
                error=errormessage,
                customer_name=CUSTOMER_NAME,
            )


@app.route("/logout", methods=["GET"])
def logout():
    """
    Logout

    Clear all session data & send user back to login page.
    """
    for key in session:
        session[key] = None
    return redirect("/login")


@app.route("/select-device", methods=["GET", "POST"])
def select_device():
    """
    Select Device

    Search / filter DNAC devices by site or name
    """
    # If not authenticated, redirect to login
    if not session.get("auth"):
        return redirect("/login")

    # On first load, reset devices
    if not session.get("dnac_devices"):
        session["dnac_devices"] = {}

    if request.method == "POST":
        # On submit of device searching form, look up devices based on
        # provided filter string
        if request.form.get("device-filter"):
            getDNACDevices(request.form.get("device-filter"))

        # On submit of device selection, save selected device &
        # redirect to vlan provisioning page
        if request.form.get("target-device"):
            session["target_device"] = request.form.get("target-device")
            return redirect("/vlan-provision")

    return render_template(
        "select-device.html",
        device_list=session.get("dnac_devices"),
    )


@app.route("/vlan-provision", methods=["GET", "POST"])
def vlan_provision():
    """
    VLAN Provisioning

    Allows user to create one or multiple VLANs, then assign VLAN ID,
    VLAN name, and which interfaces to map to each VLAN.
    """
    # If not authenticated, redirect to login
    if not session.get("auth"):
        return redirect("/login")

    # Get all stored devices
    devices = session.get("dnac_devices")

    # If form submitted, generate template & upload to DNAC
    # then push for provisioning
    if request.method == "POST":
        # Generate / Upload / Deploy template via DNAC
        generateTemplatePayload(request.json)
        uploadTemplate(
            session["template_payload"], devices[session.get("target_device")]
        )
        session["deploymentStatus"] = None
        deployTemplate(devices[session.get("target_device")])
        # Return status page after deployment is started
        return redirect("/status")

    # On first page load, query device interfaces to populate drag & drop
    if "interfaces" not in devices[session.get("target_device")].keys():
        getDeviceInterfaces(session.get("target_device"))

    return render_template(
        "vlan-provision.html",
        device=devices[session.get("target_device")],
        device_ip=session.get("target_device"),
    )


@app.route("/status", methods=["GET", "POST"])
def status():
    """
    Task Status

    Check DNA Center task status & return status page
    """
    # If not authenticated, redirect to login
    if not session.get("auth"):
        return redirect("/login")

    # If refresh button clicked, query DNAC for status
    if request.method == "POST":
        if session["templateID"]:
            # Check template deployment status...
            getTemplateDeployStatus()
            # If template was deployed successfully, delete it to keep DNAC template list clean
            if session["deploymentStatus"] == "success" and session["templateID"]:
                deleteTemplate()

    return render_template(
        "status.html",
        error=session["deploymentError"],
        status=session["deploymentStatus"],
        deployed_config=session["template_payload"],
    )


@app.route("/reset", methods=["GET"])
def reset():
    """
    Reset app

    When starting over, reset all stored session info about previous deployment
    """
    session["deploymentError"] = None
    session["deploymentStatus"] = None
    session["template_payload"] = None
    session["target_device"] = None
    session["dnac_devices"] = {}
    return redirect("/select-device")


def getDNACDevices(filter: str) -> None:
    """
    Query DNAC for device lists.

    Used to retrieve both WLCs & APs, with or without a filter
    """
    # Start DNAC session
    dnac = getDNACSession()

    # Query Devices / Filter by device family
    # Note: Filtering is case sensitive
    devices = dnac.devices.get_device_list(
        family="Switches and Hubs", hostname=f".*{filter}.*"
    )

    # Collect device info that we need to keep
    device_list = {}
    for device in devices["response"]:
        mgtIP = device["managementIpAddress"]
        device_list[mgtIP] = {}
        device_list[mgtIP]["id"] = device["instanceUuid"]
        device_list[mgtIP]["name"] = device["hostname"]
        device_list[mgtIP]["platform"] = device["platformId"]
        device_list[mgtIP]["version"] = device["softwareVersion"]
        device_list[mgtIP]["reachability"] = device["reachabilityStatus"]
        device_list[mgtIP]["family"] = device["family"]
        device_list[mgtIP]["series"] = device["series"]
        timestamp = datetime.fromtimestamp(device["lastUpdateTime"] / 1000)
        device_list[mgtIP]["lastupdate"] = timestamp.strftime("%b %d %Y, %I:%M%p")

    # Query device location
    for device in device_list:
        detailed_info = dnac.devices.get_device_detail(
            identifier="uuid", search_by=device_list[device]["id"]
        )
        device_list[device]["location"] = detailed_info["response"]["location"]

    # Store devices in session data
    session["dnac_devices"] = device_list


def getDeviceInterfaces(device_ip: str) -> None:
    """
    Query DNAC for all interfaces based on device UUID
    """
    # Start DNAC session
    dnac = getDNACSession()

    device_id = session["dnac_devices"][device_ip]["id"]

    interfaces = dnac.devices.get_interface_info_by_id(device_id)

    session["dnac_devices"][device_ip]["interfaces"] = {}

    for interface in interfaces["response"]:
        # Only select GigabitEthernet interfaces on the first module.
        # Should skip management interface, NIM slots, and AppGig interface
        if re.match("^GigabitEthernet\d\/0\/\d", interface["portName"]):
            # Store interface name to UUID mapping
            session["dnac_devices"][device_ip]["interfaces"][
                interface["portName"]
            ] = interface["id"]


def getDNACSession(user=None, passwd=None) -> api.DNACenterAPI:
    """
    General function for creating session to DNAC

    Default will use server side session credentials,
    unless specific user/password are provided
    """
    if user and passwd:
        return api.DNACenterAPI(
            username=user,
            password=passwd,
            base_url=session.get("dnac_url"),
            verify=False,
        )
    else:
        return api.DNACenterAPI(
            username=session.get("username"),
            password=session.get("password"),
            base_url=session.get("dnac_url"),
            verify=False,
        )


def getTaskStatus() -> None:
    """
    Query DNAC for task status
    """
    # Connect to DNAC
    dnac = getDNACSession()

    # Query status of task ID
    task = dnac.task.get_task_by_id(session.get("taskID"))

    # Save task response data
    session["taskStatus"] = task["response"]


def getProjectID() -> None:
    """
    General function to locate DNA Center project identifier, which will be required to
    add/remove templates.
    """
    # Connect to DNAC
    dnac = getDNACSession()
    # Query projects by name
    project = dnac.configuration_templates.get_projects(
        name=dnac_config["templates"]["project"]
    )
    # If name matches, there should only be 1 result
    project_id = project[0]["id"]
    app.logger.info(f"Found Project ID: {project_id}")
    # Store project ID
    session["projectID"] = project_id


def getTemplateID() -> None:
    """
    Looks up template ID by name
    """
    # Connect to DNAC
    dnac = getDNACSession()

    # Query template by name
    project = dnac.configuration_templates.get_projects(
        name=dnac_config["templates"]["project"]
    )
    template_id = None
    for template in project[0]["templates"]:
        if template["name"] == (
            dnac_config["templates"]["template"] + "-" + session["author"]
        ):
            template_id = template["id"]
            app.logger.info(f"Found Template ID: {template_id}")
            break
        else:
            app.logger.info("No template ID found")
    # Store template ID
    session["templateID"] = template_id


def generateTemplatePayload(new_config: dict) -> None:
    """
    Create DNA Center template with desired configuration changes
    """
    template_payload = []
    vlan_config = []
    port_config = []
    vlan_template = conf_templates.get_template("vlan.jinja2")
    port_template = conf_templates.get_template("port.jinja2")

    app.logger.info("Generating template...")
    # For each new VLAN to create...
    for entry in new_config:
        # Render the vlan.jinja2 template & append to vlan_config list
        vlan_config.append(
            vlan_template.render(
                vlan_id=new_config[entry]["vlan_id"],
                vlan_name=new_config[entry]["vlan_name"],
            )
        )
        # Render port.jinja2 template & append to port_config list
        port_list = new_config[entry]["ports"].split("\n")
        for port in port_list:
            port_config.append(
                port_template.render(
                    interface_name=port, vlan_id=new_config[entry]["vlan_id"]
                )
            )

    # Full payload is VLAN config first, followed by port config
    # including exclamation point between lines - to mimic IOS config
    template_payload = vlan_config + port_config
    template_payload = "\n!\n".join(template_payload)
    # Store full template payload in session data for now
    session["template_payload"] = template_payload
    app.logger.info("Template Generated!")


def uploadTemplate(template_payload: str, device_info: dict) -> str:
    """
    Create / Update DNA Center template
    """
    # Connect to DNAC
    dnac = getDNACSession()

    # Query project & template IDs
    getProjectID()
    getTemplateID()
    # Templates must know what device types they are intended for,
    # So we pull that from our device info
    device_types = []
    device_types.append(
        {
            "productFamily": device_info["family"],
            "productSeries": device_info["series"],
        }
    )
    # Template params includes all items we will need to provide DNAC
    # in order to create / update a template
    template_params = {
        "project_id": session["projectID"],
        "name": dnac_config["templates"]["template"] + "-" + session["author"],
        "author": session["author"],
        "softwareType": "IOS-XE",
        "deviceTypes": device_types,
        "payload": {"templateContent": template_payload},
        "version": "2",
        "language": "VELOCITY",
    }
    app.logger.info("Uploading template to DNA Center...")
    # If template already exists, push an updated version
    if session["templateID"]:
        template_params["id"] = session["templateID"]
        dnac.configuration_templates.update_template(**template_params)
        # Allow DNAC a moment to update template
        sleep(3)
        app.logger.info("Template updated.")
    # Create new if no existing template ID
    elif not session["templateID"]:
        dnac.configuration_templates.create_template(**template_params)
        # Allow DNAC a moment to create new template
        sleep(3)
        app.logger.info("Template created.")
        getTemplateID()
    # Commit new template
    app.logger.info("Committing new template version...")
    dnac.configuration_templates.version_template(
        comments="Commit via API", templateId=session["templateID"]
    )
    app.logger.info("Template committed.")
    # Allow DNAC a moment...
    sleep(3)
    app.logger.info("Template ready!")


def deployTemplate(device_info: dict) -> None:
    """
    Push new configuration template to all target devices.
    """
    app.logger.info("Starting template deployment...")

    # Connect to DNAC
    dnac = getDNACSession()

    app.logger.info(f"Deploying template to {device_info['name']}.")
    # Set list of target devices to deploy template to
    target_devices = [
        {
            "id": device_info["id"],
            "type": "MANAGED_DEVICE_UUID",
        }
    ]
    session["deploymentStatus"] = "inprogress"
    session["deploymentError"] = None
    # Deploy template
    try:
        deploy_template = dnac.configuration_templates.deploy_template(
            templateId=session["templateID"],
            targetInfo=target_devices,
        )
    except ApiError as e:
        app.logger.error("Error deploying template: ")
        app.logger.error(e)
        session["deploymentStatus"] = "fail"
        session["deploymentError"] = str(e)
        return
    # Grab deployment UUID
    session["deploy_id"] = str(deploy_template.deploymentId).split(":")[-1].strip()
    # If any errors are generated, they are included in the deploymentId field
    # So let's validate that we actually have a valid UUID - otherwise assume error
    if not re.match("^.{8}-.{4}-.{4}-.{4}-.{12}$", session["deploy_id"]):
        app.logger.error("Error deploying template: ")
        app.logger.error(deploy_template)
        session["deploymentStatus"] = "fail"
        session["deploymentError"] = deploy_template


def getTemplateDeployStatus() -> None:
    """
    Get DNAC template deployment status
    """
    app.logger.info("Checking template deployment status...")
    # Connect to DNAC
    dnac = getDNACSession()

    # Ask DNAC for currernt status of template deployment
    try:
        response = dnac.configuration_templates.get_template_deployment_status(
            deployment_id=session["deploy_id"]
        )
    except ApiError as e:
        # Some times DNAC will give 500 while querying status
        app.logger.info("Error checking deployment status:")
        app.logger.info(e)
        return

    app.logger.info(f"Deployment status: {response['status']}")
    # Check to see if deployment was successful, failed, or still in progress
    if response["status"] == "SUCCESS":
        app.logger.info("Deployment complete!")
        session["deploymentStatus"] = "success"
        session["deploymentError"] = None
    elif response["status"] == "FAILURE":
        app.logger.info("Deployment Failed! See below for errors:")
        app.logger.info(response)
        session["deploymentStatus"] = "fail"
        session[
            "deploymentError"
        ] = f"{response['devices'][0]['detailedStatusMessage']}"
    else:
        session["deploymentStatus"] = "inprogress"
        session["deploymentError"] = f"{response}"


def deleteTemplate() -> None:
    """
    Delete DNAC Template
    """
    template_name = dnac_config["templates"]["template"] + "-" + session["author"]
    if session["templateID"]:
        app.logger.info(f"Deleting template {template_name}...")
        # Connect to DNAC
        dnac = getDNACSession()
        # Delete template by ID
        try:
            dnac.configuration_templates.deletes_the_template(
                template_id=session["templateID"]
            )
        except:
            pass
        session["templateID"] = None


if __name__ == "__main__":
    # Run web app
    app.run(host="0.0.0.0", debug=True)
