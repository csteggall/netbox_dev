import re

from extras.scripts import Script, ChoiceVar, ObjectVar
from circuits.choices import CircuitStatusChoices
from circuits.models import Circuit, CircuitTermination, CircuitType
from dcim.models import Interface, Device, DeviceRole, Site, SiteGroup
from ipam.models import VLAN
from extras.scripts import ChoiceVar


class CircuitCheckingScript(Script):
    class Meta:
        name = "check on-net circuit provision"
        description = "check YDS circuit provision follows the data model"

    """ class variables """
    circuit_types = ['on-net-broadband']

    cpe_roles = [
        'cpe',
        'cpe-business',
        'cpe-residential',
    ]

    cpe_models = [
        'dx3301-t0',
        'ex5601-t0'
    ]

    demarc_devices = {
        'ethernet': ['floor-port'],
        'gpon_ubiquity': ['uf-loco'],
        'gpon_zyxel': ['pmg1005-t20c'],
        'gpen_mikrotik': ['gpen21'],
        'wifi': []
    }

    """ forms """
    circuit = ObjectVar(
        description="Select circuit to check",
        model=Circuit
    )

    architecture = ChoiceVar(
        choices=(
            ('ethernet', 'Ethernet (Cisco)'),
            ('gpon_ubiquity', 'GPON (Ubiquity)'),
            ('gpon_zyxel', 'GPON (Zyxel)'),
            ('gpen_mikrotik', 'GPEN (Mikrotik)'),
            ('wifi', 'WI-FI'),
        ),
            label="Network Architecture",
            required=True
    )

    distribution_switch = ObjectVar(
        label="Distribution Switch",
        description="Select a distribution switch",
        model=Device,
        query_params={
            'role_id': DeviceRole.objects.get(
                slug='switch').id
        },
        required=False
    )

    install_stage = ChoiceVar(
        choices=(
            ('provisioning', 'Provisioning'),
            ('installed', 'Installed'),
        ),
            label="Install Stage",
            required=True
    )

    """ helper functions for reusable code """

    def has_image(self, device):
        """
        test dcim object for uploaded images
        """
        associated_images = device.images.all()
        if associated_images:
            image_names = [str(image) for image in associated_images]
            self.log_success(
                f"{str(device.role).lower()} has associated images::"
                f" {', '.join(image_names)} "
            )
            return True
        else:
            self.log_failure(
                f"{device.role} has no associated images".lower()
            )
            return False


    def has_location(self, netbox_object, object_type: str):
        """
        netbox object has a location
        """
        if not netbox_object.location:
            self.log_failure(
                f"{object_type} not assigned to location"
            )
            return False
        else:
            self.log_success(
                f"{object_type} has location: {netbox_object.location}"
            )
            return True


    def has_site(self, netbox_object, object_type: str):
        """
        netbox object has a site
        """
        if not netbox_object.site:
            self.log_failure(
                f"{object_type} not assigned to site"
            )
            return False
        else:
            self.log_success(
                f"{object_type} has site: {netbox_object.site}"
            )
            return True


    def has_tenant(self, netbox_object, object_type: str):
        """
        netbox object has a tenant
        """
        if netbox_object.tenant:
            self.log_success(f"{object_type} has tenant:"
                             f" {netbox_object.tenant}")
            return True
        else:
            self.log_failure(f"{object_type} has no tenant")
            return False


    def has_vlan(self, device, interface: str, vlan, vlan_type: str):
        """
        check if interface has either tagged or untagged vlan
        """
        try:
            interface = Interface.objects.filter(
                device=device).get(
                name=interface
            )
        except Interface.DoesNotExist:
            self.log_failure(
                f"{interface} interface not found"
            )
            return

        vlan_assigned = getattr(interface, vlan_type, None)

        if not vlan_assigned:
            self.log_failure(
                f"{device.role} interface does not have "
                f"{vlan_type.replace('_', ' ')} "
            )
        elif vlan_assigned.id == vlan.id:
            self.log_success(
                f"{device.role} interface has the untagged vlan: {vlan.vid}"
            )
        else:
            self.log_failure(
                f"{device.role} interface does not have untagged vlan"
            )


    """ get object functions """

    def get_cpe(self, circuit):
        """
        get cpe object

        return: cpe
        """
        if not circuit.termination_z:
            return
        if not circuit.termination_z.link_peers:
            return

        cpe = circuit.termination_z.link_peers[0].device
        return cpe


    def get_vlan(self, circuit):
        """
        vlan has circuit ID as name

        return: vlan
        """
        try:
            vlan = VLAN.objects.get(name=circuit.cid)
        except VLAN.DoesNotExist:
            self.log_failure(
                f"vlan with name {circuit.cid} not found"
            )
            return
        self.log_success(
            f"vlan: {vlan.name} found"
        )
        return vlan


    """ test functions """

    def test_a_termination(self, circuit, architecture: str,):
        """
        circuit has a end termination to correct demarc depending on network
        architecture
        """
        if not circuit.termination_a:
            self.log_failure(
                f"A end termination not found"
            )
            return
        demarc_device = circuit.termination_a.link_peers
        if not demarc_device:
            self.log_failure(
                f"A end device not found"
            )
            return

        device_type = circuit.termination_a.link_peers[0].device.device_type
        if device_type.slug == self.demarc_devices[architecture]:
            self.log_success(
                f"A end termination device is correct: {device_type} "
            )
        else:
            self.log_failure(
                f"A end termination device should not be {device_type}"
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
                'circuit has no install date'
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
                    "upload speed not on Z end"
                )
            if circuit.termination_z.port_speed:
                self.log_success(
                    f"{int(circuit.termination_z.port_speed/1000)} mbs "
                    f"download speed on Z end"
                )
            else:
                self.log_failure(
                    "download speed not on Z end"
                )


    def test_circuit_status(self, circuit, install_stage: str):
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

    def test_circuit_tenant(self, circuit):
        """
        circuit has tenant
        """
        self.has_tenant(circuit, 'circuit')


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


    def test_cpe_image(self, cpe):
        """
        cpe has an uploaded image
        """
        self.has_image(cpe)


    def test_cpe_ipaddr(self, cpe):
        """
        cpe has ip address primary ip address that is assigned to y-eth
        """
        ip_addr = cpe.primary_ip4
        if not ip_addr:
            self.log_failure(
                f"cpe has no primary ip address"
            )
        else:
            self.log_success(
                f"cpe has the priamry ip address: {ip_addr}"
            )
            ip_interface = ip_addr.assigned_object
            if not ip_interface:
                self.log_failure(
                    f"ip address not assigned to interface"
                )
            elif ip_interface.name != 'Y-ETH':
                self.log_failure(
                    f"primary ip should not be assigned to {ip_interface.name}"
                )
            else:
                self.log_success(
                    f"cpe primary ip address is assigned to {ip_interface.name}"
                )


    def test_cpe_platform(self, cpe):
        """
        cpe has platform AVS
        """
        if not cpe.platform:
            self.log_failure(
                f"avsystem is not set as cpe platform"
            )
        elif cpe.platform.slug != 'avsytems':
            self.log_failure(
                f"avsystem is not set as cpe platform"
            )
        else:
            self.log_success(
                f"avsystem is set as cpe platform"
            )


    def test_cpe_role(self, cpe, ):
        """
        cpe has correct role
        """
        if cpe.device_role.slug not in self.cpe_roles:
            self.log_failure(
                f"{cpe.device_role} is not a valid device role"
            )
        else:
            self.log_success(
                f"{cpe.device_role} is a valid device role"
            )


    def test_cpe_serial(self, cpe):
        """
        cpe has serial number
        """
        if not cpe.serial:
            self.log_failure(
                f"cpe has no serial number"
            )
        else:
            self.log_success(
                f"cpe has serial number: {cpe.serial}"
            )


    def test_cpe_site_and_location(self, cpe):
        """
        cpe has site and location
        """
        if self.has_site(cpe, 'site'):
            self.has_location(cpe, 'location')


    def test_cpe_status(self, cpe, install_stage: str):
        """
        cpe status is staged if provisioning or active if installed
        """
        if install_stage == 'provisioning':
            if cpe.status != 'planned':
                self.log_failure(
                    f"cpe is in {cpe.status} state, should be in "
                    f"staged"
                )
            else:
                self.log_success('cpe is in planned state')
        elif install_stage == 'installed':
            if cpe.status != 'active':
                self.log_failure(
                    f"cpe is in {cpe.status} state, should be active"
                )
            else:
                self.log_success(
                    f"cpe is in an active state"
                )


    def test_cpe_tenant(self, cpe):
        """
        cpe has tenant
        """
        self.has_tenant(cpe, 'cpe')


    def test_cpe_type(self, cpe):
        """
        cpe type is in standard list
        """
        if cpe.device_type.slug not in self.cpe_models:
            self.log_failure(
                f"{cpe.device_type} is not a standard issue on-net broadband cpe "
                f"model"
            )
        else:
            self.log_success(
                f"cpe is of type: {cpe.device_type}"
            )


    def test_ip_mask(self, cpe):
        """
        ip address is /32
        """
        ip_addr = cpe.primary_ip4
        if not ip_addr:
            return
        subnet_mask = str(ip_addr).split('/')[1]
        if subnet_mask != '32':
            self.log_failure(
                f"{ip_addr} is not a /32"
            )
        else:
            self.log_success(
                f"ip is a /32"
            )


    def test_libre_id(self, cpe):
        """
        cpe has a libre id
        """
        if not cpe.cf['libre_id']:
            self.log_failure(
                f"cpe has no libre id"
            )
        else:
            self.log_success(
                f"device has libre id: {cpe.cf['libre_id']}"
            )


    def test_vlan_cpe(self, vlan, circuit):
        """
        cpe has untagged vlan on its Y-ETH interface
        """
        cpe = self.get_cpe(circuit)
        if not cpe:
            return

        self.has_vlan(cpe, 'Y-ETH', vlan, 'untagged_vlan')


    def test_vlan_site(self, vlan):
        """
        vlan has a site
        """
        self.has_site(vlan, 'vlan')


    def test_vlan_svi(self, vlan, distribution_switch):
        """
        svi is correctly named and exists untagged on distribution switch
        """
        svi_name = 'Vlan' + str(vlan.vid)

        self.has_vlan(distribution_switch, svi_name, vlan, 'untagged_vlan')


    def test_vlan_tenant(self, vlan):
        """
        cpe has tenant
        """
        self.has_tenant(vlan, 'vlan')


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
        else:
            link_peer = circuit.termination_z.link_peers[0]
            if not str(link_peer.device.role.slug) in self.cpe_roles:
                self.log_failure(
                    f'{link_peer.device.role} is not a valid cpe role'
                )
            elif not str(link_peer.name) == 'Y-ETH':
                self.log_failure(
                    f"cpe interface is type {link_peer.name}, should be Y-ETH"
                )
            else:
                self.log_success(
                    f'z end termination has a valid cpe '
                    'role',
                )
            return link_peer


    def run(self, data, commit):
        """
        script logic
        """
        circuit = data['circuit']
        architecture = data['architecture']
        distribution_switch = data['distribution_switch']
        install_stage = data['install_stage']
        self.log_info(f"{install_stage}")

        if str(circuit.type.slug) not in self.circuit_types:
            self.log_failure(
                f"this is not a circuit of type on-net broadband"
            )

        elif install_stage == 'provisioning':

            """circuit and termination checks"""
            self.test_circuit_ref(circuit)
            self.test_circuit_status(circuit, install_stage)
            self.test_circuit_tenant(circuit)
            self.test_circuit_type(circuit)
            self.test_circuit_provider(circuit)
            self.test_circuit_speeds(circuit)
            self.test_a_termination(circuit, architecture)
            self.test_z_termination(circuit)

            """cpe checks"""
            cpe = self.get_cpe(circuit)
            if cpe:
                self.test_cpe_tenant(cpe)
                self.test_cpe_site_and_location(cpe)
                self.test_cpe_type(cpe)
                self.test_cpe_serial(cpe)
                self.test_cpe_platform(cpe)
                self.test_cpe_role(cpe)
                self.test_circuit_status(circuit, install_stage)

                """ip address"""
                self.test_cpe_ipaddr(cpe)
                self.test_ip_mask(cpe)

            """vlan checks"""
            vlan = self.get_vlan(circuit)
            if vlan:
                self.test_vlan_tenant(vlan)
                self.test_vlan_site(vlan)
                self.test_vlan_cpe(vlan, circuit)
                self.test_vlan_svi(vlan, distribution_switch)


            if architecture == 'copper_cisco':
                ...
            if architecture == 'gpon_ubiquity':
                ...
            if architecture == 'gpon_zyxel':
                ...
            if architecture == 'gpen_mikrotik':
                ...
            if architecture == 'wifi':
                ...


        elif install_stage == 'installed':

            cpe = self.get_cpe(circuit)
            self.test_circuit_install_date(circuit)
            self.test_libre_id(cpe)
            self.test_cpe_image(cpe)
            self.test_circuit_status(circuit, install_stage)


            if architecture == 'copper_cisco':
                ...
            if architecture == 'gpon_ubiquity':
                ...
            if architecture == 'gpon_zyxel':
                ...
            if architecture == 'gpen_mikrotik':
                ...
            if architecture == 'wifi':
                ...


        """complete"""
        self.log_info(f"completed all checks for circuit: {circuit}.")
