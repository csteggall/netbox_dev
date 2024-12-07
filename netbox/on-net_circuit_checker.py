"""
get from user:
-circuit reference
-order stage
    -provisioning
    -installed
-infrastructure:
    -copper (Cisco),
    -GPON (Ubiquity),
    -GPON (Zyxel),
    -GPEN (Microtik),
    -WI-FI

--PROVISIONING--
X-circuit reference is YDS-xxx-xx-cuid and cuid is unique
X-circuit has tenant
X-circuit has status planned
X-circuit has A end termination
    -matches site account code
-circuit has Z end termination
    -matches site account code
X-circuit has YDS as provider
X-circuit speeds on Z end
X-circuit speeds not on A end

X-circuit Z end termination has device with type CPE connected
X-interface is Y-ETH

-CPE has tenant
-CPE has site
-CPE has location
-CPE of type DX3301-T0 or EX5601
-CPE has serial number
-CPE has role CPE-Business or CPE-Residential
-CPE has platform AVSystem
-CPE has Status Staged
-CPE has primary ip address

-Y-ETH has ip address assigned
-IP address is /32

-untagged vlan on Y-ETH
-untagged vlan on ds switch SVI

-circuit A end termination has device of type onu, as switch, ds switch, ptp
or media converter

if ONU:
-onu has tenant
-onu has site
-onu has location
-onu has asset tag
-onu status planned
-onu is of device type UF-LOCO or PMG1005-T20C
-untagged vlan on PON and LAN interface
-tagged vlan on both ends of OLT uplink
-PON port has link peer
if fibre presentation present:
-PON port connected to front port of fibre presentation

if copper:
-untagged vlan on switch port
-if switch port is as switch, tagged vlan on trunk ports
-CPE y-eth has link peer
if copper presentation present:
-cpe y-eth connected to front port of copper presentation
else:
-cpe y-eth connected to as switch

if ptp:
...

--INSTALLED--
X-circuit has install date
X-cpe has image
X-cpe has status: active
X-cpe has libre device id

if ONU:
-ONU has image
-onu status active
-fibre presentation present in location
-fibre presentation has image
-PON port connected to front port of fibre presentation

if copper:
-copper presentation present in location
-copper presentation has image
-cpe y-eth connected to front port of copper presentation

if ptp:
-ptp has image

---FURTHER FEATURES---
-correct alerting status on libre
-can only run the script for installed circuit if provisioning scipt has
been passed
-provisiong script have a 'by-pass' checkbox so can run the installed script
even if it has failed
"""

import re

from extras.scripts import Script, ChoiceVar, ObjectVar
from circuits.choices import CircuitStatusChoices, CircuitTerminationPortSpeedChoices
from circuits.models import Circuit, CircuitTermination, CircuitType
from dcim.models import Interface, Device, Site, SiteGroup
from ipam.models import VLAN
from extras.scripts import ChoiceVar


class CircuitCheckingScript(Script):
    class Meta:
        name = "check on-net circuit provision"
        description = "check YDS circuit provision follows the data model"

    circuit_types = ['on-net-broadband']

    cpe_roles = [
        'cpe',
        'cpe-business',
        'cpe-residential',
    ]

    circuit = ObjectVar(
        description="Select circuit to check",
        model=Circuit
    )

    infrastructure = ChoiceVar(
        choices=(
            ('copper_cisco', 'copper (Cisco)'),
            ('gpon_ubiquity', 'GPON (Ubiquity)'),
            ('gpon_zyxel', 'GPON (Zyxel)'),
            ('gpen_mikrotik', 'GPEN (Mikrotik)'),
            ('wifi', 'WI-FI'),
        ),
            label="Network Infrastructure",
            required=True
    )

    install_stage = ChoiceVar(
        choices=(
            ('provisioning', 'Provisioning'),
            ('installed', 'Installed'),
        ),
            label="Install Stage",
            required=True
    )


    def get_cpe(self, circuit):
        """
        get cpe from circuit
        """

        cpe = circuit.termination_z.link_peers[0].device
        return cpe


    def has_image(self, device):
        """
        test dcim object for uploaded images
        """
        associated_images = device.images.all()
        if associated_images:
            image_names = [str(image) for image in associated_images]
            self.log_success(
                f"{str(device.role).lower()} has images:"
                f" {', '.join(image_names)} "
            )
        else:
            self.log_failure(
                f"{device.role} has no associated images".lower()
            )

    def has_tenant(self, netbox_object):
        """
        test netbox object has a tenant
        """
        if netbox_object.tenant:
            self.log_success(f"{netbox_object} has tenant:"
                             f" {netbox_object.tenant}")
        else:
            self.log_failure(f"{object} has no tenant")


    def test_a_termination(self, circuit):
        """
        circuit has a end termination
        """
        if not circuit.termination_a:
            self.log_failure(
                f"no A end termination"
            )


    def test_circuit_install_date(self, circuit):
        """
        circuit has an install date
        """
        if circuit.install_date:
            self.log_success(
                f'circuit has install date of {circuit.install_date}'
            )
        else:
            self.log_failure(
                'no install date'
            )

    def test_circuit_provider(self, circuit):
        """
        circuit has YDS as provider
        """
        if str(circuit.provider) in ['York Data Services']:
            self.log_success(f'circuit has the provider: {circuit.provider}')
        else:
            self.log_failure(
                f"{circuit.provider} listed as provider, should be York Data Services "
            )


    def test_circuit_ref(self, circuit):
        """
        circuit has correctly formatted YDS-xxx-xx-xxxx circuit reference,
        has valid site account code
        has YDS provider account code
        has unique circuit identifier
        """

        """circuit is of format YDS-xxx-xx-xxxx"""
        match = re.fullmatch(
            r"YDS-\d\d\d-\d\d-(\d\d\d\d)",
            circuit.cid
        )
        if not match:
            self.log_failure(
                f"{circuit.cid} is not of the format YDS-xxx-xx-xxxx"
            )

        """circuit has a valid site account code"""
        # get all on-net sites
        on_net_parent_group = SiteGroup.objects.get(slug='on-net-sites')
        on_net_child_groups = list(
            SiteGroup.objects.filter(
                parent=on_net_parent_group.id
            )
        )
        on_net_sites = list(
            Site.objects.filter(
                group__in=on_net_child_groups
            )
        )

        # create list of on-net account codes
        on_net_account_codes = [
            on_net_site.cf['account_code']
            for on_net_site in on_net_sites
            if on_net_site.cf['account_code']
        ]

        # check circuit ref to make sure on-net account code is valid
        pattern = (r"\w\w\w-(" + "|".join(on_net_account_codes) +
                   r")-\d\d-\d\d\d\d")
        if not re.match(pattern, circuit.cid):
            self.log_failure(
                f"on-net site code used in circuit reference not found"
            )

        """provider code is 01 for YDS"""
        pattern = r"\w\w\w-\d\d\d-01-\d\d\d\d"
        if not re.match(pattern, circuit.cid):
            self.log_failure(
                f"provider code in circuit reference should be 01"
            )

        """circuit identifier is unique"""
        existing_yds_circuits = Circuit.objects.filter(
            cid__istartswith='YDS',
            status=CircuitStatusChoices.STATUS_ACTIVE
        )

        cuid = circuit.cid.split('-')[-1]

        existing_cuids = []
        for existing_yds_circuit in existing_yds_circuits:
            existing_cuid = existing_yds_circuit.cid.split('-')[-1]
            existing_cuids.append(existing_cuid)
        if existing_cuids.count(cuid) > 1:
            self.log_failure(
                f"cuid: {cuid} is not unique"
            )


    def test_circuit_speeds(self, circuit):
        """
        upload/down speed is not on A end termination
        upload/download speed is on Z end termination
        """
        if circuit.termination_a:
            if circuit.termination_a.port_speed:
                self.log_failure(
                    f"download speed is on A end"
                )
            if circuit.termination_a.upstream_speed:
                self.log_failure(
                    f"upload speed is on A end"
                )

        if circuit.termination_z:
            if circuit.termination_z.upstream_speed:
                self.log_success(
                    f"{int(circuit.termination_z.upstream_speed/1000)} mbs "
                    f"upload on Z end"
                )
            else:
                self.log_failure(
                    "no upload on Z end"
                )
            if circuit.termination_z.port_speed:
                self.log_success(
                    f"{int(circuit.termination_z.port_speed/1000)} mbs "
                    f"download on Z end"
                )
            else:
                self.log_failure(
                    "no download on Z end"
                )


    def test_circuit_status(self, circuit, install_stage):
        """
        circuit status is planned if provisioning or active if installed
        """
        if install_stage == 'provisioning':
            if circuit.status != 'planned':
                self.log_failure(
                    f"circuit is in {circuit.status} state, should be in "
                    f"planned"
                )
            else:
                self.log_success('circuit is in planned state')
        elif install_stage == 'installed':
            if circuit.status != 'active':
                self.log_failure(
                    f"circuit is in {circuit.status} state, should be active"
                )
            else:
                self.log_success(
                    f"circuit is in an active state"
                )


    def test_circuit_type(self, circuit):
        """
        circuit is of type 'on-net-broadband'
        """
        if str(circuit.type.slug) in self.circuit_types:
            self.log_success(f"circuit is of type {circuit.type}")
        else:
            self.log_failure(
                f"on-net broadband should not be of type {circuit.type}"
            )


    def test_image_cpe(self, circuit):
        """
        cpe has an uploaded image
        """
        device = circuit.termination_z.link_peers[0].device
        self.has_image(device)


    def test_libre_id(self, circuit):
        """
        cpe has a libre id
        """
        cpe = circuit.termination_z.link_peers[0].device
        if not cpe.cf['libre_id']:
            self.log_failure(
                f"cpe has no libre id"
            )
        else:
            self.log_success(
                f"device has libre id: {cpe.cf['libre_id']}"
            )


    def test_z_termination(self, circuit):
        """
        circuit has a z end termination connected to a cpe and interface Y-ETH
        """
        if not circuit.termination_z:
            self.log_failure(
                f'no Z end termination',
            )
        elif not circuit.termination_z.link_peers:
            self.log_failure(
                f'no Z end termination device',
            )
        link_peer = circuit.termination_z.link_peers[0]
        if not str(link_peer.device.role.slug) in self.cpe_roles:
            self.log_failure(
                f'{link_peer.device.role} is not a valid cpe role'
            )
        elif not str(link_peer.name) == 'Y-ETH':
            self.log_failure(
                f"interface is type {link_peer.name}, should be Y-ETH"
            )
        else:
            self.log_success(
                f'z end termination device has a valid cpe '
                'role',
            )


    def run(self, data, commit):
        """
        script logic
        """
        circuit = data['circuit']
        install_stage = data['install_stage']
        self.log_info(f"{install_stage}")

        if str(circuit.type.slug) not in self.circuit_types:
            self.log_failure(
                f"this is not a circuit of type on-net broadband"
            )

        elif install_stage == 'provisioning':

            """circuit and termination checks"""
            self.test_circuit_ref(circuit)
            self.has_tenant(circuit)
            self.test_circuit_type(circuit)
            self.test_circuit_provider(circuit)
            self.test_circuit_speeds(circuit)
            self.test_a_termination(circuit)
            self.test_z_termination(circuit)
            self.test_circuit_status(circuit, install_stage)

            """cpe checks"""


        elif install_stage == 'installed':

            self.test_circuit_install_date(circuit)
            self.test_libre_id(circuit)
            self.test_image_cpe(circuit)
            self.test_circuit_status(circuit, install_stage)



        self.log_info(f"completed all checks for circuit: {circuit}.")
2