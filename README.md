# Catalyst Center - VLAN / Port provisioning

[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/gve-sw/gve_devnet_dnac_vlan_provisioning)

This repository contains sample code for deploying interface VLAN configuration to Cisco Catalyst Center via a simplified web interface. This allows someone to create new VLANs & assign them to switch interfaces, without needing to access Catalyst Center or have knowledge of the underlying device configuration.

The web application walks through the following workflow:

- Select a Catalyst Center appliance & log in
- Search Catalyst Center for network switches using a hostname filter
- Use a web form to create new VLANs, then drag & drop interfaces to each VLAN
- Deploy the provided VLAN/interface configuration to the target device via Catalyst Center templates
- Monitor Catalyst Center template deployment status & view configuration summary

## Contacts

- Matt Schmitz (<mattsc@cisco.com>)

## Solution Components

- Catalyst Center
- Catalyst Switching
- Python / Flask

## Installation/Configuration

### **Step 1 - Clone repo:**

```bash
git clone <repo_url>
```

### **Step 2 - Install required dependancies:**

```bash
pip install -r requirements.txt
```

### **Step 3 - Provide Catalyst Center list**

In order to use this script, a YAML file of DNAC addresses must be provided. This file must be named `dna-servers.yml`. This file also contains the provisioning project & template names.

A sample file has been provided (`example_dna-servers.yml`). The configuration takes the following format:

```
servers:
  <DNAC hostname>
    alias: <Friendly alias>
    address: <IP address>
templates:
  project: <DNAC Project name>
  template: <Name of templates to be created by script>

# For example:
servers:
  server-name-01:
    alias: DNA 01
    address: 10.10.10.10
  server-name-02:
    alias: DNA 02
    address: 10.20.20.20
templates:
  project: DNAC_Project
  template: api_port_vlan_config
```

### **Step 4 - Provide Port / VLAN config templates**

Within the `config_templates` directory, there are two sample Jinja2 templates - `port.jinja2` and `vlan.jinja2`. Open each file & fill in the desired device configuration interfaces & VLANs. These templates are rendered using Jinja2 before being deployed to the device. Available variables are:

- `{{interface_name}}`
- `{{vlan_name}}`
- `{{vlan_id}}`

### **Step 5 - (Optional) Configure Authentication Mode**

A few additional items may be configured via environment variables. Environment variables can be passed via docker or a local `.env` file in the code directory.

There are two authentication modes for this web app, single or multiple.

Single authentication mode is the default and will be used if no other configuration is specified. In this mode, the web app user provides their DNA-C login credentials - and that user account is used for all subsequent API calls to Catalyst Center.

Multiple authentication mode is intended to be used in situations where the end user does not have API write access to Catalyst Center. In this mode, the user still logs into the web app with their own DNA-C user account. However, these credentials are only used to authenticate to DNA-C & ensure the user has access. All subsequent API calls are performed by a separate DNA-C service account with write access to the API. This ensures that the end user can accomplish the provisioning without their Catalyst Center account requiring API write privileges.

Multiple authentication can be configured by setting the following environment variables:

- `APP_MODE=MULTIAUTH` - Sets app to multi-auth mode
- `DNAC_USER=` - Username of service account with API write permissions
- `DNAC_PASS=` - Password of service account with API write permissions

## Usage

### Running locally

Run the application with the following command:

```
python3 app.py
```

Reach Flask UI at: `http://127.0.0.1:5000`

### Run with Docker

A docker image has been published for this container at ghcr.io/gve-sw/gve_devnet_dnac_vlan_provisioning

This image can be used by creating the config & .env files as specified above - then providing them to the container image:

`docker run -v <path-to-dna-servers.yaml>:/app/dna-servers.yaml -p 5000:5000 -d ghcr.io/gve-sw/gve_devnet_dnac_vlan_provisioning:latest`

If config templates also need to be overwritten, add `-v <path-to-config_templates-directory>:/app/config_templates/`

Alternatively, a docker-compose.yml file has been included as well.

# Related Sandbox

- [Cisco Catalyst Center Lab](https://devnetsandbox.cisco.com/RM/Diagram/Index/b8d7aa34-aa8f-4bf2-9c42-302aaa2daafb?diagramType=Topology)

# Screenshots

### Step 1 - Selecting a device

![/IMAGES/step_1.png](/IMAGES/step_1.png)

### Step 2 - Create VLAN / Assign Ports

![/IMAGES/step_2.png](/IMAGES/step_2.png)

### Step 3 - Deployment Status

![/IMAGES/step_3.png](/IMAGES/step_3.png)

### LICENSE

Provided under Cisco Sample Code License, for details see [LICENSE](LICENSE.md)

### CODE_OF_CONDUCT

Our code of conduct is available [here](CODE_OF_CONDUCT.md)

### CONTRIBUTING

See our contributing guidelines [here](CONTRIBUTING.md)

#### DISCLAIMER

<b>Please note:</b> This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use.
You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.
