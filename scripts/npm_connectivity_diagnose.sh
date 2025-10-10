#!/usr/bin/env bash
# Comprehensive diagnostics for npm connectivity issues.
# Generates a timestamped log summarizing environment, npm configuration,
# networking status, DNS resolution, TLS setup, and reachability tests.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/npm_connectivity_diagnostics_${TIMESTAMP}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "===================================================================="
echo "NPM CONNECTIVITY DIAGNOSTICS"
echo "Started at: ${start_time} UTC"
echo "Log file: ${LOG_FILE}"
echo "===================================================================="
echo

section() {
    echo
    echo "--------------------------------------------------------------------"
    echo "$1"
    echo "--------------------------------------------------------------------"
}

run_cmd() {
    local description="$1"
    shift
    local cmd=("$@")
    echo
    echo "### ${description}"
    echo "Command: ${cmd[*]}"
    if ! command -v "${cmd[0]}" >/dev/null 2>&1; then
        echo "Status: SKIPPED (command not found)"
        return 127
    fi
    local start end rc
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "Start: ${start} UTC"
    "${cmd[@]}"
    rc=$?
    end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "End: ${end} UTC"
    echo "Exit status: ${rc}"
    return $rc
}

section "System information"
run_cmd "Operating system details" uname -a
run_cmd "Distribution release info" lsb_release -a
run_cmd "Kernel version" cat /proc/version
run_cmd "Current user" id
run_cmd "Environment variables (npm & proxy relevant)" bash -lc "env | sort | grep -E '^(NPM|NODE|HTTP_|HTTPS_|NO_)?(CONFIG_)?'"
run_cmd "Working directory" pwd
run_cmd "Filesystem disk usage" df -h

section "Node.js and npm versions"
run_cmd "Node.js version" node --version
run_cmd "npm version" npm --version
run_cmd "npx version" npx --version

section "npm configuration"
run_cmd "npm config get registry" npm config get registry
run_cmd "npm config list" npm config list -l
run_cmd "npm proxy" npm config get proxy
run_cmd "npm https-proxy" npm config get https-proxy
run_cmd "npm cafile" npm config get cafile
run_cmd "npm prefix" npm config get prefix
run_cmd "Global npmrc" cat /etc/npmrc
run_cmd "User npmrc" cat "$HOME/.npmrc"
run_cmd "Project npmrc" cat "$(pwd)/.npmrc"

section "Network configuration"
run_cmd "IP configuration" ip addr
run_cmd "Routing table" ip route
run_cmd "DNS configuration" cat /etc/resolv.conf
run_cmd "Hosts file" cat /etc/hosts
run_cmd "Network interfaces" ls -l /sys/class/net
run_cmd "Firewall status (ufw)" ufw status
run_cmd "Firewall status (iptables)" iptables -L -n -v

section "Connectivity tests"
run_cmd "Ping 1.1.1.1" ping -c 4 -W 2 1.1.1.1
run_cmd "Ping 8.8.8.8" ping -c 4 -W 2 8.8.8.8
run_cmd "Ping registry.npmjs.org" ping -c 4 -W 2 registry.npmjs.org
run_cmd "Traceroute registry.npmjs.org" traceroute -n registry.npmjs.org
run_cmd "DNS lookup (dig) registry.npmjs.org" dig registry.npmjs.org
run_cmd "DNS lookup (nslookup) registry.npmjs.org" nslookup registry.npmjs.org
run_cmd "Resolve via getent" getent hosts registry.npmjs.org
run_cmd "TCP connectivity (nc) to registry 443" nc -vz registry.npmjs.org 443
run_cmd "TCP connectivity (nc) to registry 80" nc -vz registry.npmjs.org 80
run_cmd "Curl HEAD registry" curl -I --max-time 30 https://registry.npmjs.org/
run_cmd "Curl verbose registry" curl -v --max-time 30 https://registry.npmjs.org/ -o /dev/null
run_cmd "Curl to npmjs.com" curl -I --max-time 30 https://www.npmjs.com/
run_cmd "OpenSSL TLS check" openssl s_client -connect registry.npmjs.org:443 -servername registry.npmjs.org </dev/null

section "npm registry interactions"
run_cmd "npm ping" npm ping --registry https://registry.npmjs.org/
run_cmd "npm view example package" npm view npm version --registry https://registry.npmjs.org/
run_cmd "npm install dry-run example" npm install --ignore-scripts --prefer-offline --dry-run npm

section "System certificate stores"
run_cmd "List CA certificates" ls -l /etc/ssl/certs
run_cmd "OpenSSL version" openssl version -a
run_cmd "NSS shared certdb" ls -l /etc/pki/nssdb
run_cmd "Certificate fingerprint for registry" bash -lc "openssl s_client -connect registry.npmjs.org:443 -servername registry.npmjs.org </dev/null | openssl x509 -noout -issuer -subject -dates -fingerprint"

section "Proxy and network environment"
run_cmd "Print proxy env vars" bash -lc "env | grep -i proxy"
run_cmd "curl via http_proxy" curl -I --max-time 30 http://registry.npmjs.org/
run_cmd "Check npmrc files" find "$HOME" -maxdepth 2 -name '*.npmrc' -print
run_cmd "Check git config proxy" git config --global --get http.proxy
run_cmd "Check git config https proxy" git config --global --get https.proxy

section "Container / virtualization"
run_cmd "Docker info" docker info
run_cmd "Cgroup info" cat /proc/1/cgroup
run_cmd "dmesg recent network errors" bash -lc "dmesg | tail -n 200"

section "Summary"
echo "Diagnostics complete at: $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC"
echo "Exit statuses above indicate success (0) or failure (>0) for each command."
echo "Please review the sections above for clues about npm install connectivity issues."

echo
section "Log file path"
echo "Results stored in: ${LOG_FILE}"
echo "===================================================================="
