#!/usr/bin/env bash
# Prepare the Ubuntu-hosted VM's distro-provided sandbox for Lake's inert checker.
set -euo pipefail

probe() {
  /usr/bin/bwrap --unshare-all --die-with-parent --new-session \
    --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp -- /bin/true
}
if [[ -x /usr/bin/bwrap ]] && probe; then
  exit 0
fi

sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends bubblewrap
if probe; then
  exit 0
fi

# Ubuntu Noble can permit creation of a user namespace while denying the
# capabilities needed to initialize its isolated loopback interface. Load the
# distro's optional profile for bubblewrap alone, then repeat the kernel probe.
sudo apt-get install -y --no-install-recommends apparmor-profiles
sudo apparmor_parser -r /usr/share/apparmor/extra-profiles/bwrap-userns-restrict
probe
