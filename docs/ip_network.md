# README – Netzwerkarchitektur Raspberry Pi (Event-Gateway)

## Zweck
Der Raspberry Pi dient als **zentrales Event-Gateway** für ein Kassensystem.
Er stellt ein **eigenes, isoliertes LAN** für Kassen, Tablets und Drucker bereit
und routet dieses optional über ein bestehendes WLAN ins Internet.

Der Fokus liegt auf:
- Stabilität
- Offline-Fähigkeit
- Reboot-Sicherheit
- Einfacher Bedienung am Event

---

## Gesamtarchitektur (Übersicht)

```mermaid
flowchart LR
    subgraph Event-LAN["Event-LAN (192.168.50.0/24)"]
        K1[Kasse / Tablet]
        K2[Kasse / Tablet]
        D1[Bondrucker]
        SW[Switch]
    end

    subgraph RaspberryPi["Raspberry Pi – Event-Gateway"]
        ETH[eth0<br/>192.168.50.1]
        DNS[dnsmasq<br/>DHCP + DNS]
        NAT[NAT / Routing]
    end

    subgraph Uplink["Bestehendes WLAN"]
        WLAN[wlan0<br/>DHCP]
        NET[Internet]
    end

    K1 --> SW
    K2 --> SW
    D1 --> SW
    SW --> ETH
    ETH --> DNS
    DNS --> NAT
    NAT --> WLAN
    WLAN --> NET


---

## Netzwerkrollen

### Interfaces

| Interface | Funktion                                  |
| --------- | ----------------------------------------- |
| eth0      | Event-LAN (statisch, Gateway für Clients) |
| wlan0     | Uplink ins bestehende WLAN (DHCP)         |

---

## IP- und Adresskonzept

| Element                    | Wert                           |
| -------------------------- | ------------------------------ |
| LAN-Netz                   | 192.168.50.0/24                |
| Raspberry Pi (Gateway/DNS) | 192.168.50.1                   |
| DHCP-Bereich               | 192.168.50.50 – 192.168.50.150 |

---

## Statische IP auf eth0

* Umsetzung mit **systemd-networkd**
* eth0 erhält die IP **auch ohne eingesteckte Clients**
* Reboot-sicher

Datei:

```
/etc/systemd/network/10-eth0-static.network
```

```ini
[Match]
Name=eth0

[Network]
Address=192.168.50.1/24
ConfigureWithoutCarrier=yes
```

---

## DHCP & DNS (dnsmasq)

* Dienst: **dnsmasq**
* DHCP **nur auf eth0**
* DNS lokal + Weiterleitung ins WLAN
* Robustes Startverhalten (`bind-dynamic`)

### DNS-Aliases (LAN-intern)

Zur einfachen Bedienung am Event sind feste DNS-Aliases definiert:

| Alias     | Ziel         |
| --------- | ------------ |
| kasse     | 192.168.50.1 |
| kasse.lan | 192.168.50.1 |

Zugriff:

* `http://kasse`
* `http://kasse.lan`
* `http://192.168.50.1` (Fallback)

➡️ Der System-Hostname des Raspberry Pi bleibt unverändert.

---

## Routing & Internetzugang

* IPv4-Forwarding aktiviert
* NAT (Masquerading) von Event-LAN → WLAN
* Umsetzung mit `iptables`
* Regeln persistent gespeichert (`netfilter-persistent`)

➡️ Internetzugang ist **optional**
➡️ Kassensystem funktioniert **offline vollständig weiter**

---

## Boot- und Reboot-Verhalten

Nach einem Neustart sind automatisch aktiv:

* systemd-networkd (eth0 IP)
* dnsmasq (DHCP & DNS)
* IP-Forwarding
* iptables NAT-Regeln


---

## Offline-Betrieb

* DHCP, DNS und internes Routing funktionieren ohne Internet
* Nur externe Dienste sind bei fehlendem WLAN nicht erreichbar
* Lokaler Zugriff immer möglich

---

## Quick-Checks (Technik)

```bash
ip -4 addr show eth0
systemctl is-active dnsmasq
sysctl net.ipv4.ip_forward
iptables -t nat -S POSTROUTING
```

---

## Notfallkonfiguration (Client manuell)

| Einstellung  | Wert          |
| ------------ | ------------- |
| IP           | 192.168.50.10 |
| Subnetzmaske | 255.255.255.0 |
| Gateway      | 192.168.50.1  |
| DNS          | 192.168.50.1  |

---

## Einsatzbereich

* Event-Kassensystem
* Vereinsanlässe
* Temporäre Infrastruktur
* Umgebung mit unzuverlässigem Internet

