
# get from user:
- circuit reference
- architecture:  
    - copper (Cisco),  
    - GPON (Ubiquity),  
    - GPON (Zyxel),
    - GPEN (Microtik),  
    - WI-FI  
- distribution switch
- order stage  
    - provisioning  
    - installed  

# PROVISIONING
- [x] circuit reference is YDS-xxx-xx-cuid and cuid is unique  
- [x] circuit has tenant  
- [ ] circuit has status planned  
- [ ] circuit has A end termination
- [ ] matches site account code  
- [ ] circuit has Z end termination  
- [ ] matches site account code  
- [x] circuit has YDS as provider  
- [x] circuit speeds on Z end  
- [x] circuit speeds not on A end  

- [x] circuit Z end termination has device with type CPE connected
- [x] interface is Y-ETH

- [x] CPE has tenant
- [x] CPE has site
- [x] CPE has location
- [x] CPE of type DX3301-T0 or EX5601
- [x] CPE has serial number
- [x] CPE has role CPE-Business or CPE-Residential
- [x] has platform AVSystem
- [x] has Status Staged
- [x] has primary ip address

- [x] Y-ETH has ip address assigned
- [x] IP address is /32

- [x] vlan had circuit ref as name
- [x] vlan has tenant
- [x] vlan has site
    - site matches circuit site

- [x] untagged vlan on Y-ETH
- [x] untagged vlan on ds switch SVI

- [x] circuit A end termination has device of type ubiq onu, zyxel onu,
floor-port, ptp or media convert

## if ONU:
- [ ] onu has tenant
- [ ] onu has site
- [ ] onu has location
- [ ] onu has asset tag
- [ ] onu status planned
- [ ] onu is of device type UF-LOCO or PMG1005-T20C
- [ ] untagged vlan on PON and LAN interface
- [ ] tagged vlan on both ends of OLT uplink
- [ ] PON port has link peer
### if fibre presentation present:
- [ ] PON port connected to front port of fibre presentation

## if copper:
- [ ] untagged vlan on switch port
- [ ] if switch port is accesss switch, tagged vlan on trunk ports
- [ ] CPE y-eth has link peer
### if copper presentation present:
- [ ] cpe y-eth connected to front port of copper presentation
### else:
- [ ] cpe y-eth connected to as switch

## if ptp:
...

# INSTALLED
- [x] circuit has install date
- [x] cpe has image
- [x] cpe has status: active
- [x] cpe has libre device id

## if ONU:
- [ ] ONU has image
- [ ] onu status active
- [ ] fibre presentation present in location
- [ ] fibre presentation has image
- [ ] PON port connected to front port of fibre presentation

## if copper:
- [ ] copper presentation present in location
- [ ] copper presentation has image
- [ ] cpe y-eth connected to front port of copper presentation

## ptp:
- [ ] ptp has image

# FURTHER FEATURES
- [ ] correct alerting status on libre
- [ ] can only run the script for installed circuit if provisioning scipt has
been passed
- [ ] provisiong script have a 'by-pass' checkbox so can run the installed script
even if it has failed
