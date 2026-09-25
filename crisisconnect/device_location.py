"""One-shot OS location access. Coordinates remain in memory and are never logged."""
import asyncio
from dataclasses import dataclass
import json
import math
import subprocess
import sys
import time

from .public_data import check_cancel


@dataclass(frozen=True)
class LocationReading:
    status: str  # available, disabled, denied, unavailable
    latitude: float = 0
    longitude: float = 0
    accuracy_m: float = 0


def validated_reading(lat, lon, accuracy, age):
    values = tuple(map(float, (lat, lon, accuracy, age)))
    lat, lon, accuracy, age = values
    if not all(math.isfinite(v) for v in values) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return LocationReading("unavailable")
    if not 0 <= accuracy <= 1000 or not 0 <= age <= 120:
        return LocationReading("unavailable")
    return LocationReading("available", lat, lon, accuracy)


class DeviceLocation:
    def read(self, cancel=None):
        check_cancel(cancel)
        try:
            if sys.platform == "win32":
                result = self.windows()
            elif sys.platform.startswith("linux"):
                result = asyncio.run(self.linux())
            else:
                result = LocationReading("unavailable")
        except Exception:
            result = LocationReading("unavailable")
        check_cancel(cancel)
        return result

    @staticmethod
    def windows():
        # Fixed command; no user text is interpolated into PowerShell.
        script = r'''
Add-Type -AssemblyName System.Device
$watcher = New-Object System.Device.Location.GeoCoordinateWatcher
try {
    $ready = $watcher.TryStart($false, [TimeSpan]::FromSeconds(15))
    if ($watcher.Permission -eq 'Denied') { @{status='denied'} | ConvertTo-Json -Compress }
    elseif ($watcher.Status -eq 'Disabled') { @{status='disabled'} | ConvertTo-Json -Compress }
    elseif ($ready -and -not $watcher.Position.Location.IsUnknown) {
        $point = $watcher.Position.Location
        @{status='available'; lat=$point.Latitude; lon=$point.Longitude;
          accuracy=$point.HorizontalAccuracy; age=([DateTimeOffset]::UtcNow-$watcher.Position.Timestamp).TotalSeconds} | ConvertTo-Json -Compress
    } else { @{status='unavailable'} | ConvertTo-Json -Compress }
} finally { $watcher.Dispose() }
'''
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, timeout=22,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            return LocationReading("unavailable")
        value = json.loads(result.stdout)
        if value["status"] != "available":
            return LocationReading(value["status"])
        return validated_reading(value["lat"], value["lon"], value["accuracy"], value["age"])

    @staticmethod
    async def linux():
        # GeoClue permissions are owned by the desktop's location agent.
        from dbus_next.aio import MessageBus
        from dbus_next import BusType, Variant
        bus = None
        client = None
        try:
            async with asyncio.timeout(20):
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
                name = "org.freedesktop.GeoClue2"

                async def proxy(path):
                    return bus.get_proxy_object(name, path, await bus.introspect(name, path))

                manager = (await proxy("/org/freedesktop/GeoClue2/Manager")).get_interface(name + ".Manager")
                path = await manager.call_get_client()
                obj = await proxy(path)
                props = obj.get_interface("org.freedesktop.DBus.Properties")
                await props.call_set(name + ".Client", "DesktopId", Variant("s", "crisisconnect"))
                await props.call_set(name + ".Client", "RequestedAccuracyLevel", Variant("u", 6))
                client = obj.get_interface(name + ".Client")
                await client.call_start()
                while True:
                    location = (await props.call_get(name + ".Client", "Location")).value
                    if location != "/":
                        loc = (await proxy(location)).get_interface("org.freedesktop.DBus.Properties")
                        fields = await loc.call_get_all(name + ".Location")
                        return validated_reading(fields["Latitude"].value, fields["Longitude"].value,
                                                 fields["Accuracy"].value, time.time() - fields["Timestamp"].value[0])
                    await asyncio.sleep(0.25)
        except Exception as exc:
            denied = "AccessDenied" in str(getattr(exc, "type", ""))
            return LocationReading("denied" if denied else "unavailable")
        finally:
            if client:
                try:
                    await asyncio.wait_for(client.call_stop(), 2)
                except Exception:
                    pass
            if bus:
                bus.disconnect()
