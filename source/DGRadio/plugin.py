# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import os
import time
import threading
import urllib.request
import urllib.parse
import hashlib
import re
import unicodedata
import subprocess
import tempfile

UPDATE_URL = "https://raw.githubusercontent.com/dorinelu/DGRadio/main/updates/stable.json"
UPDATE_CACHE = "/tmp/dgradio-update-lastcheck"

from enigma import (
    eServiceReference, eTimer, iServiceInformation,
    eListboxPythonMultiContent, gFont, ePicLoad, ePoint,
    RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_VALIGN_CENTER
)
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.Sources.StaticText import StaticText
from Components.config import config, configfile, ConfigSubsection, ConfigYesNo, ConfigSelection, getConfigListEntry
from Tools.LoadPixmap import LoadPixmap
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen

try:
    from enigma import addFont
    addFont(os.path.join(os.path.dirname(__file__), "DGRadioMonoCondensed.ttf"), "DGRadioMonoCondensed", 100, 0)
    _DG_LCD_FONT = "DGRadioMonoCondensed"
except Exception as err:
    print("[DGRadio] Pixel font unavailable: %s" % err)
    _DG_LCD_FONT = "Regular"

PLUGIN_NAME = "DG Radio"
PLUGIN_VERSION = "0.2"
PLUGIN_RELEASE = "r50"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/DGRadio"
STATIONS_FILE = os.path.join(PLUGIN_PATH, "stations.json")
COUNTRIES_FILE = os.path.join(PLUGIN_PATH, "countries.json")
FALLBACK_LOGO = os.path.join(PLUGIN_PATH, "plugin.png")
FALLBACK_ART = os.path.join(PLUGIN_PATH, "fallback_art.png")

def _load_country_manifest():
    fallback = [
        {"code": "ro", "name": "Romania", "file": "stations_ro.json", "itunes_country": "RO"},
        {"code": "de", "name": "Germany", "file": "stations_de.json", "itunes_country": "DE"},
    ]
    try:
        with open(COUNTRIES_FILE, "r") as handle:
            data = json.load(handle)
        countries = data.get("countries", []) if isinstance(data, dict) else []
        valid = []
        seen = set()
        for item in countries:
            code = str(item.get("code", "")).strip().lower()
            name = str(item.get("name", "")).strip()
            filename = str(item.get("file", "")).strip()
            if not code or not name or not filename or code in seen:
                continue
            seen.add(code)
            valid.append({
                "code": code,
                "name": name,
                "file": filename,
                "itunes_country": str(item.get("itunes_country", code.upper())).strip().upper(),
            })
        return valid or fallback
    except Exception as err:
        print("[DGRadio] Country manifest unavailable: %s" % err)
        return fallback

COUNTRIES = _load_country_manifest()
COUNTRY_MAP = dict((item["code"], item) for item in COUNTRIES)
COUNTRY_CHOICES = [(item["code"], item["name"]) for item in COUNTRIES]
LOGO_CACHE = "/etc/enigma2/dgradio/logos"
ARTWORK_CACHE = "/tmp/dgradio-artwork"
WEATHER_CACHE = "/tmp/dgradio-weather.json"
OAWEATHER_ICON_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/OAWeather/Icons"
WEATHER_REFRESH = 1800

# Station artwork found on the web. Logos are downloaded only on demand and cached
# on the receiver; the plugin itself does not bundle third-party station artwork.
STATION_LOGOS = {
    "digifm": "https://www.digifm.ro/static/theme-repo/bin/images/logo-digifm.png",
    "kissfm": "https://cdn.adh.reperio.news/image-a/a81718e2-bf17-4a31-aa48-00148102154a/index.jpeg?p=f%3Djpeg%26w%3D1400%26r%3Dcontain",
    "magicfm": "https://i0.1616.ro/media/601/3161/38616/19550057/1/logo-magic-fm.png",
    "rockfm": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/91/83/ef/9183eff1-8bc7-c9a3-7aba-6171cc03e629/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "radiozu": "https://static-media.streema.com/media/cache/98/a8/98a8368e449a23b143f0b4c868d1e836.jpg",
    "virginradio": "https://i1.sndcdn.com/artworks-YM9cx0HLLY6hk2ur-uxW9Wg-t500x500.jpg",
    "radioimpuls": "https://cdn.knd.ro/media/521/2942/1730/20375771/1/radio-impuls--crop-1704895377.jpg?height=675&width=1200",
    "profm": "https://s.iw.ro/gateway/g/ZmlsZVNvdXJjZT1odHRwJTNBJTJGJTJG/c3RvcmFnZTA2dHJhbnNjb2Rlci5yY3Mt/cmRzLnJvJTJGc3RvcmFnZSUyRjIwMjAl/MkYwOSUyRjE1JTJGMTIyODAzMl8xMjI4/MDMyX0xPR08tUFJPRk0tT1BFTi1SQURJ/Ty0yLmpwZyZ3PTgwMCZoYXNoPWY3MWQ4/NzI0YzJlNmRiOTMzOWIwNmE5NGI1MTJjZDI2.thumb.jpg",
    "europafm": "https://i1.sndcdn.com/avatars-000376654298-emy6by-t1080x1080.jpg",
    "rfiromania": "https://cdn-profiles.tunein.com/s8821/images/logog.png?t=1",
    "rra": "https://cdn-profiles.tunein.com/s66900/images/logog.png?t=158835",
    "rrcultural": "https://static.srr.ro/images/gaudeamus/exhibitor/11/exhibit-logo-1941-rrc.png",
    "rrmuzical": "https://www.romania-actualitati.ro/img.php?c=1&h=540&u=https%3A%2F%2Fwww.romania-actualitati.ro%2Fuploads%2Fmodules%2Fnews%2F0%2F2025%2F3%2F24%2F208115%2F1742819928f9b12918.jpg&w=960",
    "radioiasi": "https://static.srr.ro/images/gaudeamus/exhibitor/381/exhibit-logo-21851-logo-radio-iasi.png",
    "radiocluj": "https://images.operacluj.ro/2021/02/logo-radio-ro-cluj.png",
    "radioconstanta": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Logo_Radio_Rom%C3%A2nia_Constan%C8%9Ba_%282008%29.svg/960px-Logo_Radio_Rom%C3%A2nia_Constan%C8%9Ba_%282008%29.svg.png",
    "radiotimisoara": "https://zenoimages.s3.us-west-001.backblazeb2.com/d5317412-c7f3-4815-b308-4ab1bdc51aec/images/logo",
    "radiooltenia": "https://static.srr.ro/images/gaudeamus/exhibitor/401/exhibit-logo-24281-logo-roc.png",
    "bucurestifm": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Logo%20Radio%20Rom%C3%A2nia%20Bucure%C8%99ti%20FM%20%282008%29.svg?width=960",
}

if not hasattr(config.plugins, "dgradioro"):
    config.plugins.dgradioro = ConfigSubsection()
if not hasattr(config.plugins.dgradioro, "restore_service"):
    config.plugins.dgradioro.restore_service = ConfigYesNo(default=True)
if not hasattr(config.plugins.dgradioro, "autoplay"):
    config.plugins.dgradioro.autoplay = ConfigYesNo(default=False)
if not hasattr(config.plugins.dgradioro, "country"):
    config.plugins.dgradioro.country = ConfigSelection(default="ro", choices=COUNTRY_CHOICES)

if not hasattr(config.plugins.dgradioro, "check_updates"):
    config.plugins.dgradioro.check_updates = ConfigYesNo(default=True)
if not hasattr(config.plugins.dgradioro, "frontpanel"):
    config.plugins.dgradioro.frontpanel = ConfigSelection(default="auto", choices=[
        ("auto", "Automatic"), ("off", "Off (system display)"),
        ("station", "Station only"), ("track", "Station + Track"),
        ("full", "Full (artwork when supported)")])

try:
    from .DGFrontPanel import detect as detectFrontPanel, describe as describeFrontPanel, DGRadioSummary
except Exception as err:
    print("[DGRadio] Front panel module unavailable: %s" % err)
    DGRadioSummary = None
    def detectFrontPanel():
        return dict(model="unknown", type="unknown", profile="none", width=0, height=0)
    def describeFrontPanel(caps):
        return "Front panel unavailable"


def _safe(value):
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _codec_text(station):
    codec = _safe(station.get("codec") or "-")
    bitrate = station.get("bitrate_kbps")
    if bitrate:
        return "%s %s kbps" % (codec, bitrate)
    return codec


def _station_row(index, station, is_current=False):
    """Retro fixed-column row. The station actually playing is white; others are green."""
    h = 32
    number = "%02d." % (index + 1)
    name = _safe(station.get("name"))
    group = _safe(station.get("group"))
    codec = _codec_text(station)
    green = 0x39D353
    white = 0xF5F1E8
    normal = white if is_current else green
    return [
        index,
        MultiContentEntryText(pos=(8, 0), size=(55, h), font=0,
                              flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=number, color=normal, color_sel=white),
        MultiContentEntryText(pos=(68, 0), size=(430, h), font=0,
                              flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=name, color=normal, color_sel=white),
        MultiContentEntryText(pos=(505, 0), size=(210, h), font=0,
                              flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=group, color=normal, color_sel=white),
        MultiContentEntryText(pos=(725, 0), size=(263, h), font=0,
                              flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=codec, color=normal, color_sel=white),
    ]


class StationList(MenuList):
    def __init__(self, rows=None):
        MenuList.__init__(self, rows or [], True, eListboxPythonMultiContent)
        self.l.setFont(0, gFont("Regular", 20))
        self.l.setItemHeight(32)

    def setStations(self, stations, current_id=None):
        self.setList([_station_row(i, st, _safe(st.get("id")) == _safe(current_id)) for i, st in enumerate(stations)])


def _version_key(text):
    # Numeric release ordering: r47 > r46, never lexicographic r9 > r10.
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?-r(\d+)$", str(text or ""), re.I)
    if not match:
        return None
    return tuple(int(x or 0) for x in match.groups())


def _fetch_public_update():
    req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": "DGRadio-Enigma2/0.2"})
    with urllib.request.urlopen(req, timeout=7) as response:
        if response.geturl().split(":", 1)[0] != "https":
            raise ValueError("Insecure update manifest redirect")
        payload = response.read(32769)
    if len(payload) > 32768:
        raise ValueError("Update manifest too large")
    data = json.loads(payload.decode("utf-8"))
    if (not isinstance(data, dict) or data.get("app") != "DGRadio"
            or data.get("internal") is not False or data.get("channel") != "public"):
        raise ValueError("Invalid public update manifest")
    version = str(data.get("version", ""))
    if _version_key(version) is None:
        raise ValueError("Invalid update version")
    url = str(data.get("ipk_url", ""))
    if not url.startswith("https://raw.githubusercontent.com/dorinelu/DGRadio/") or not url.endswith(".ipk"):
        raise ValueError("Unexpected download URL")
    sha = str(data.get("sha256", ""))
    if not re.match(r"^[a-fA-F0-9]{64}$", sha):
        raise ValueError("Missing SHA-256 hash")
    data["changelog"] = [str(x)[:180] for x in data.get("changelog", []) if isinstance(x, str)][:6]
    return data


def _installed_version():
    return _version_key("%s-%s" % (PLUGIN_VERSION, PLUGIN_RELEASE))


def _update_text(info):
    notes = "\n".join("- " + item for item in info.get("changelog", []))
    return ("A new DG Radio version is available!\n\n"
            "Installed: %s-%s\nNew: %s\n\nWhat's new:\n%s\n\n"
            "Install update now?" % (PLUGIN_VERSION, PLUGIN_RELEASE,
            info.get("display_version", info["version"]), notes or "Maintenance update"))


def _download_install_update(info):
    # This method runs only after the user explicitly approves the update.
    url = info["ipk_url"]
    expected = info["sha256"].lower()
    limit = 20 * 1024 * 1024
    folder = tempfile.mkdtemp(prefix="dgradio-update-")
    path = os.path.join(folder, "update.ipk")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DGRadio-Updater/0.2"})
        digest = hashlib.sha256()
        total = 0
        with urllib.request.urlopen(req, timeout=25) as response:
            if not response.geturl().startswith("https://raw.githubusercontent.com/dorinelu/DGRadio/"):
                raise ValueError("Untrusted download redirect")
            with open(path, "wb") as output:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("Update is too large")
                    digest.update(chunk)
                    output.write(chunk)
        if total != int(info.get("size_bytes", -1)):
            raise ValueError("Download size mismatch")
        if digest.hexdigest() != expected:
            raise ValueError("SHA-256 checksum mismatch; installation cancelled")
        proc = subprocess.run(["opkg", "install", path], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=150, universal_newlines=True)
        if proc.returncode:
            raise RuntimeError("opkg failed (%d): %s" % (proc.returncode, proc.stdout[-1200:]))
        return "Installation completed. Restart Enigma2 GUI to load the new version."
    finally:
        shutil_rmtree_safe(folder)


def shutil_rmtree_safe(path):
    # Avoid dependencies on external shell utilities.
    try:
        for filename in os.listdir(path):
            os.unlink(os.path.join(path, filename))
        os.rmdir(path)
    except Exception:
        pass


class DGUpdateMixin(object):
    def _initUpdater(self, startup=False):
        self._dg_result = None
        self._dg_busy = False
        self._dg_startup = startup
        self._dg_closed = False
        self._dg_timer = eTimer()
        self._dg_timer.callback.append(self._pollUpdate)
        self.onClose.append(self._closeUpdater)
        if startup:
            self.onLayoutFinish.append(self._checkStartupUpdate)

    def _closeUpdater(self):
        self._dg_closed = True
        self._dg_timer.stop()

    def _checkStartupUpdate(self):
        if not config.plugins.dgradioro.check_updates.value:
            return
        now = time.time()
        try:
            with open(UPDATE_CACHE, "r") as f:
                last = float(f.read().strip())
        except Exception:
            last = 0
        if 0 <= now - last < 86400:
            return
        try:
            with open(UPDATE_CACHE, "w") as f:
                f.write(str(now))
        except Exception:
            pass
        self._runUpdateCheck(silent=True)

    def _runUpdateCheck(self, silent=False):
        if self._dg_busy or self._dg_closed:
            return
        self._dg_busy = True
        self._dg_result = None
        self._dg_silent = silent
        def worker():
            try:
                result = ("check", True, _fetch_public_update())
            except Exception as err:
                result = ("check", False, str(err))
            self._dg_result = result
        threading.Thread(target=worker, daemon=True).start()
        self._dg_timer.start(250, False)

    def _pollUpdate(self):
        if self._dg_closed or self._dg_result is None:
            return
        kind, ok, result = self._dg_result
        self._dg_result = None
        self._dg_busy = False
        self._dg_timer.stop()
        if kind == "install":
            if ok:
                self.session.openWithCallback(self._restartReply, MessageBox,
                    result + "\n\nRestart Enigma2 GUI now?", MessageBox.TYPE_YESNO)
            else:
                self.session.open(MessageBox, "DG Radio update failed:\n%s" % result,
                                  MessageBox.TYPE_ERROR)
            return
        if not ok:
            if not self._dg_silent:
                self.session.open(MessageBox, "Could not check updates:\n%s" % result,
                                  MessageBox.TYPE_ERROR)
            return
        if _version_key(result["version"]) <= _installed_version():
            if not self._dg_silent:
                self.session.open(MessageBox,
                    "DG Radio is up to date for the public channel.\nInstalled: %s-%s\nPublic: %s" %
                    (PLUGIN_VERSION, PLUGIN_RELEASE, result["version"]), MessageBox.TYPE_INFO)
            return
        self._dg_candidate = result
        self.session.openWithCallback(self._approveUpdate, MessageBox,
                                      _update_text(result), MessageBox.TYPE_YESNO)

    def _approveUpdate(self, approved):
        if not approved or self._dg_closed or self._dg_busy:
            return
        info = self._dg_candidate
        self._dg_busy = True
        self._dg_result = None
        def worker():
            try:
                result = ("install", True, _download_install_update(info))
            except Exception as err:
                result = ("install", False, str(err))
            self._dg_result = result
        threading.Thread(target=worker, daemon=True).start()
        self._dg_timer.start(250, False)
        self.session.open(MessageBox, "Downloading and installing DG Radio update...",
                          MessageBox.TYPE_INFO, timeout=4)

    def _restartReply(self, confirmed):
        if confirmed:
            from Screens.Standby import TryQuitMainloop
            self.session.open(TryQuitMainloop, 3)


class DGSettings(Screen, ConfigListScreen, DGUpdateMixin):
    skin = """
        <screen name="DGSettings" position="center,center" size="920,470" title="DG Radio - Settings" backgroundColor="#07101A">
            <eLabel position="0,0" size="920,5" backgroundColor="#2A8CFF" zPosition="-10" />
            <widget name="title" position="35,28" size="850,50" font="Regular;32" foregroundColor="#F4F7FA" transparent="1" zPosition="5" />
            <widget name="config" position="35,105" size="850,220" scrollbarMode="showOnDemand" zPosition="5" />
            <widget name="hint" position="35,342" size="850,39" font="Regular;20" foregroundColor="#A9B8C8" transparent="1" zPosition="5" />
            <eLabel position="35,393" size="850,1" backgroundColor="#394657" zPosition="2" />
            <ePixmap position="40,414" size="22,22" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/ball_red.png" alphatest="blend" zPosition="10" />
            <widget source="key_red" render="Label" position="72,407" size="150,38" font="Regular;23" foregroundColor="#F1F3F6" transparent="1" zPosition="10" />
            <ePixmap position="350,414" size="22,22" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/ball_yellow.png" alphatest="blend" zPosition="10" />
            <widget source="key_yellow" render="Label" position="383,407" size="250,38" font="Regular;23" foregroundColor="#F1F3F6" transparent="1" zPosition="10" />
            <ePixmap position="775,414" size="22,22" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/ball_green.png" alphatest="blend" zPosition="10" />
            <widget source="key_green" render="Label" position="809,407" size="100,38" font="Regular;23" foregroundColor="#F1F3F6" transparent="1" zPosition="10" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        entries = [
            getConfigListEntry("Restore previous TV/radio service when leaving", config.plugins.dgradioro.restore_service),
            getConfigListEntry("Autoplay selected station when plugin opens", config.plugins.dgradioro.autoplay),
            getConfigListEntry("Station list / country", config.plugins.dgradioro.country),
            getConfigListEntry("Front panel (takes effect after reopening plugin)", config.plugins.dgradioro.frontpanel),
            getConfigListEntry("Check for public updates on startup", config.plugins.dgradioro.check_updates),
        ]
        ConfigListScreen.__init__(self, entries, session=session)
        self["title"] = Label("DG Radio - Settings")
        self["hint"] = Label("Detected front panel: " + describeFrontPanel(detectFrontPanel()))
        self["key_red"] = StaticText("Cancel")
        self["key_yellow"] = StaticText("Check for Updates")
        self["key_green"] = StaticText("Save")
        self._initUpdater(startup=False)
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.keyCancel,
            "red": self.keyCancel,
            "green": self.saveSettings,
            "yellow": self.checkForUpdates,
        }, -2)

    def checkForUpdates(self):
        self._runUpdateCheck(silent=False)

    def saveSettings(self):
        for entry in self["config"].list:
            entry[1].save()
        configfile.save()
        self.close(True)


class DGRadio(Screen, DGUpdateMixin):
    # Explicit zPosition is intentional. Some Enigma2 skins draw eLabel rectangles
    # above widgets if both use the default z-order.
    skin = """
        <screen name="DGRadio" position="center,center" size="1180,950" flags="wfNoBorder" backgroundColor="#202033">
            <!-- subtle Winamp-style outer bevel: lighter top/left, darker bottom/right -->
            <eLabel position="0,0" size="1180,3" backgroundColor="#52516B" zPosition="-40" />
            <eLabel position="0,0" size="3,950" backgroundColor="#52516B" zPosition="-40" />
            <eLabel position="0,947" size="1180,3" backgroundColor="#090911" zPosition="-40" />
            <eLabel position="1177,0" size="3,950" backgroundColor="#090911" zPosition="-40" />
            <!-- WINAMP-style main title band: double gold rails + 3 decorative window buttons -->
            <eLabel position="14,12" size="1152,38" backgroundColor="#0D0D1A" zPosition="-20" />
            <eLabel position="14,12" size="1152,1" backgroundColor="#777389" zPosition="-14" />
            <eLabel position="14,49" size="1152,1" backgroundColor="#080810" zPosition="-14" />
            <eLabel position="26,18" size="358,3" backgroundColor="#E6C86D" zPosition="-5" />
            <eLabel position="26,26" size="358,3" backgroundColor="#B89C38" zPosition="-5" />
            <eLabel position="796,18" size="278,3" backgroundColor="#E6C86D" zPosition="-5" />
            <eLabel position="796,26" size="278,3" backgroundColor="#B89C38" zPosition="-5" />
            <widget name="appTitle" position="394,13" size="392,30" font="Regular;22" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <eLabel position="1086,17" size="20,20" backgroundColor="#D9C69A" zPosition="0" />
            <eLabel position="1088,19" size="16,16" backgroundColor="#4B463E" zPosition="1" />
            <widget name="mainMin" position="1088,18" size="16,17" font="Regular;15" halign="center" foregroundColor="#F3D47E" transparent="1" zPosition="10" />
            <eLabel position="1114,17" size="20,20" backgroundColor="#D9C69A" zPosition="0" />
            <eLabel position="1116,19" size="16,16" backgroundColor="#4B463E" zPosition="1" />
            <widget name="mainShade" position="1116,17" size="16,18" font="Regular;15" halign="center" foregroundColor="#F3D47E" transparent="1" zPosition="10" />
            <eLabel position="1142,17" size="20,20" backgroundColor="#D9C69A" zPosition="0" />
            <eLabel position="1144,19" size="16,16" backgroundColor="#4B463E" zPosition="1" />
            <widget name="mainClose" position="1144,17" size="16,18" font="Regular;15" halign="center" foregroundColor="#F3D47E" transparent="1" zPosition="10" />
            <widget name="version" position="0,0" size="1,1" font="Regular;1" transparent="1" zPosition="10" />
            <widget name="subtitle" position="0,0" size="1,1" font="Regular;1" transparent="1" zPosition="10" />

            <!-- FRAME 1: station / metadata / clock -->
            <eLabel position="14,56" size="760,160" backgroundColor="#2C2A40" zPosition="-20" />
            <eLabel position="14,56" size="760,2" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="14,56" size="2,160" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="14,214" size="760,2" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="772,56" size="2,160" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="28,68" size="736,96" backgroundColor="#020507" zPosition="-10" />
            <!-- Static dot-matrix texture, not an audio visualizer -->
            <ePixmap position="28,68" size="736,96" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/winamp_lcd_dots.png" alphatest="off" zPosition="-8" />
            <widget name="stationLogo" position="40,74" size="145,84" alphatest="blend" scale="1" zPosition="10" />
            <widget name="logoFallback" position="40,101" size="145,30" font="Regular;17" halign="center" foregroundColor="#777889" transparent="1" zPosition="9" />
            <!-- R29: compact Winamp LCD styling without synthetic visualizers. -->
            <eLabel position="196,74" size="2,83" backgroundColor="#454354" zPosition="1" />
            <widget name="station" position="207,73" size="353,32" font="Regular;24" foregroundColor="#E8E4D7" transparent="1" zPosition="10" />
            <eLabel position="206,105" size="357,1" backgroundColor="#30332D" zPosition="1" />
            <widget name="metadata" position="207,107" size="360,29" font="DGRadioMonoCondensed;23" foregroundColor="#49F15C" transparent="1" zPosition="10" />
            <widget name="streaminfo" position="207,139" size="355,23" font="Regular;16" foregroundColor="#C0B995" transparent="1" zPosition="10" />
            <!-- The clock sits directly on the shared dot-matrix LCD, with no separate panel. -->
            <widget name="clock" position="552,93" size="200,40" font="DGRadioMonoCondensed;32" halign="right" foregroundColor="#4BFA60" transparent="1" zPosition="10" />

            <!-- transport remains inside frame 1 -->
            <eLabel position="28,173" size="736,36" backgroundColor="#171624" zPosition="-10" />
            <!-- Transport controls: single pre-rendered Winamp Classic strip (no custom renderer) -->
            <ePixmap position="46,176" size="424,30" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/transport_classic.png" alphatest="off" zPosition="4" />
            <widget name="remoteHint" position="492,180" size="105,24" font="Regular;15" halign="center" foregroundColor="#9A98A8" transparent="1" zPosition="10" />
            <widget name="state" position="630,180" size="115,24" font="Regular;16" halign="right" foregroundColor="#20F84C" transparent="1" zPosition="10" />

            <!-- FRAME 2: weather, auto-located by public IP -->
            <eLabel position="14,225" size="760,155" backgroundColor="#2C2A40" zPosition="-20" />
            <eLabel position="14,225" size="760,2" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="14,225" size="2,155" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="14,378" size="760,2" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="772,225" size="2,155" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="26,236" size="736,29" backgroundColor="#0D0D1A" zPosition="-10" />
            <eLabel position="26,236" size="736,1" backgroundColor="#68647B" zPosition="-5" />
            <eLabel position="26,264" size="736,1" backgroundColor="#090914" zPosition="-5" />
            <widget name="weatherTitle" position="42,237" size="110,24" font="Regular;18" halign="left" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <widget name="weatherHeaderInfo" position="160,238" size="590,22" font="Regular;13" halign="right" foregroundColor="#A9A7B8" transparent="1" zPosition="10" />

            <widget name="weatherCurrentIcon" position="38,276" size="72,72" alphatest="blend" scale="1" zPosition="10" />
            <widget name="weatherTemp" position="120,270" size="108,42" font="Regular;31" foregroundColor="#F5F1E8" transparent="1" zPosition="10" />
            <widget name="weatherTodayRange" position="222,280" size="94,26" font="Regular;16" halign="right" foregroundColor="#D7D5E2" transparent="1" zPosition="10" />
            <widget name="weatherCity" position="120,309" size="190,25" font="Regular;18" foregroundColor="#F5F1E8" transparent="1" zPosition="10" />
            <widget name="weatherDetails" position="120,335" size="195,20" font="Regular;14" foregroundColor="#A9A7B8" transparent="1" zPosition="10" />
            <widget name="weatherExtra" position="120,355" size="195,18" font="Regular;13" foregroundColor="#A9A7B8" transparent="1" zPosition="10" />

            <eLabel position="320,274" size="1,88" backgroundColor="#4A4962" zPosition="-5" />
            <widget name="weatherDay1" position="332,270" size="130,22" font="Regular;17" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <widget name="weatherIcon1" position="372,294" size="52,52" alphatest="blend" scale="1" zPosition="10" />
            <widget name="weatherTemp1" position="332,346" size="130,22" font="Regular;16" halign="center" foregroundColor="#D7D5E2" transparent="1" zPosition="10" />

            <eLabel position="466,274" size="1,88" backgroundColor="#4A4962" zPosition="-5" />
            <widget name="weatherDay2" position="478,270" size="130,22" font="Regular;17" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <widget name="weatherIcon2" position="518,294" size="52,52" alphatest="blend" scale="1" zPosition="10" />
            <widget name="weatherTemp2" position="478,346" size="130,22" font="Regular;16" halign="center" foregroundColor="#D7D5E2" transparent="1" zPosition="10" />

            <eLabel position="612,274" size="1,88" backgroundColor="#4A4962" zPosition="-5" />
            <widget name="weatherDay3" position="624,270" size="130,22" font="Regular;17" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <widget name="weatherIcon3" position="664,294" size="52,52" alphatest="blend" scale="1" zPosition="10" />
            <widget name="weatherTemp3" position="624,346" size="130,22" font="Regular;16" halign="center" foregroundColor="#D7D5E2" transparent="1" zPosition="10" />

            <!-- FRAME 3: large album artwork spanning both left frames -->
            <eLabel position="785,56" size="381,324" backgroundColor="#2C2A40" zPosition="-20" />
            <eLabel position="785,56" size="381,2" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="785,56" size="2,324" backgroundColor="#4A4962" zPosition="-15" />
            <eLabel position="785,378" size="381,2" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="1164,56" size="2,324" backgroundColor="#11101B" zPosition="-15" />
            <eLabel position="797,68" size="357,29" backgroundColor="#0D0D1A" zPosition="-10" />
            <eLabel position="797,68" size="357,1" backgroundColor="#68647B" zPosition="-5" />
            <eLabel position="797,96" size="357,1" backgroundColor="#090914" zPosition="-5" />
            <widget name="artTitle" position="820,69" size="311,24" font="Regular;18" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <eLabel position="797,96" size="357,278" backgroundColor="#090A10" zPosition="-10" />
            <widget name="albumArt" position="803,100" size="345,270" alphatest="blend" scale="1" zPosition="10" />
            <widget name="artFallback" position="815,220" size="320,30" font="Regular;16" halign="center" foregroundColor="#777889" transparent="1" zPosition="9" />

            <!-- playlist -->
            <eLabel position="14,390" size="1152,552" backgroundColor="#26253A" zPosition="-20" />
            <eLabel position="26,400" size="1128,29" backgroundColor="#0D0D1A" zPosition="-10" />
            <eLabel position="26,400" size="1128,1" backgroundColor="#68647B" zPosition="-5" />
            <eLabel position="26,428" size="1128,1" backgroundColor="#090914" zPosition="-5" />
            <eLabel position="38,405" size="380,3" backgroundColor="#E6C86D" zPosition="-5" />
            <eLabel position="38,413" size="380,3" backgroundColor="#B89C38" zPosition="-5" />
            <eLabel position="762,405" size="338,3" backgroundColor="#E6C86D" zPosition="-5" />
            <eLabel position="762,413" size="338,3" backgroundColor="#B89C38" zPosition="-5" />
            <widget name="playlistTitle" position="430,401" size="320,24" font="Regular;18" halign="center" foregroundColor="#F2E7CA" transparent="1" zPosition="10" />
            <eLabel position="1110,404" size="18,18" backgroundColor="#D9C69A" zPosition="0" />
            <eLabel position="1112,406" size="14,14" backgroundColor="#4B463E" zPosition="1" />
            <widget name="playlistShade" position="1112,404" size="14,17" font="Regular;13" halign="center" foregroundColor="#F3D47E" transparent="1" zPosition="10" />
            <eLabel position="1136,404" size="18,18" backgroundColor="#D9C69A" zPosition="0" />
            <eLabel position="1138,406" size="14,14" backgroundColor="#4B463E" zPosition="1" />
            <widget name="playlistClose" position="1138,404" size="14,17" font="Regular;13" halign="center" foregroundColor="#F3D47E" transparent="1" zPosition="10" />
            <widget name="headNo" position="34,433" size="55,22" font="Regular;15" foregroundColor="#8A8999" transparent="1" zPosition="10" />
            <widget name="headStation" position="95,433" size="430,22" font="Regular;15" foregroundColor="#8A8999" transparent="1" zPosition="10" />
            <widget name="headType" position="532,433" size="210,22" font="Regular;15" foregroundColor="#8A8999" transparent="1" zPosition="10" />
            <widget name="headCodec" position="752,433" size="263,22" font="Regular;15" foregroundColor="#8A8999" transparent="1" zPosition="10" />
            <!-- Winamp Classic playlist scrollbar, custom-drawn to avoid skin scrollbar overrides -->
            <widget name="list" position="28,458" size="1102,445" scrollbarMode="showNever" foregroundColor="#39D353" foregroundColorSelected="#FFFFFF" backgroundColor="#020507" backgroundColorSelected="#28458A" zPosition="10" />
            <eLabel position="1133,458" size="20,445" backgroundColor="#555369" zPosition="9" />
            <eLabel position="1135,460" size="16,441" backgroundColor="#10101D" zPosition="10" />
            <eLabel position="1136,461" size="14,16" backgroundColor="#CFC8B6" zPosition="11" />
            <eLabel position="1138,463" size="10,12" backgroundColor="#817E83" zPosition="12" />
            <widget name="scrollUp" position="1138,461" size="10,16" font="Regular;11" halign="center" foregroundColor="#12121C" transparent="1" zPosition="13" />
            <eLabel position="1136,885" size="14,16" backgroundColor="#CFC8B6" zPosition="11" />
            <eLabel position="1138,887" size="10,12" backgroundColor="#817E83" zPosition="12" />
            <widget name="scrollDown" position="1138,885" size="10,16" font="Regular;11" halign="center" foregroundColor="#12121C" transparent="1" zPosition="13" />
            <widget name="winampScrollThumb" position="1136,479" size="14,46" backgroundColor="#A9A597" foregroundColor="#D8D1BD" transparent="0" zPosition="15" />
            <widget name="winampScrollGrip" position="1140,497" size="6,10" backgroundColor="#555361" transparent="0" zPosition="16" />

            <!-- Classic Winamp footer: single bevelled metallic control strip -->
            <ePixmap position="28,909" size="1128,37" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/DGRadio/footer_classic.png" alphatest="on" zPosition="8" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.frontpanel_caps = detectFrontPanel()
        self.frontpanel_mode = config.plugins.dgradioro.frontpanel.value
        self.fp_artist = ""
        self.fp_title = ""
        print("[DGRadio] Front panel: %s; mode=%s" % (describeFrontPanel(self.frontpanel_caps), self.frontpanel_mode))
        self.old_service = self.session.nav.getCurrentlyPlayingServiceReference()
        self.stations = []
        self.current_station = None
        self.current_index = 0
        self.started_at = None
        self.playing = False
        self.paused = False
        self.logo_pending = None
        self.logo_loading = set()
        self.logo_current_id = None
        self.picload = ePicLoad()
        try:
            self.picload.PictureData.get().append(self._logoDecoded)
        except Exception:
            try:
                self.picload.PictureData.connect(self._logoDecoded)
            except Exception:
                pass

        self.artwork_pending = None
        self.artwork_loading = set()
        self.artwork_miss = set()
        self.artwork_current_key = None
        self.last_nowplaying_key = None
        self.showing_station_fallback = False
        self.artload = ePicLoad()
        self.weather_pending = None
        self.weather_loading = False
        self.weather_last_request = 0
        self.weather_data = None
        try:
            self.artload.PictureData.get().append(self._artDecoded)
        except Exception:
            try:
                self.artload.PictureData.connect(self._artDecoded)
            except Exception:
                pass

        self["appTitle"] = Label("DG RADIO  V%s-%s" % (PLUGIN_VERSION, PLUGIN_RELEASE.upper()))
        self["subtitle"] = Label("")
        self["mainMin"] = Label("_")
        self["mainShade"] = Label("▼")
        self["mainClose"] = Label("X")
        self["eqShade"] = Label("▼")
        self["eqClose"] = Label("X")
        self["artShade"] = Label("▼")
        self["artClose"] = Label("X")
        self["playlistShade"] = Label("▼")
        self["playlistClose"] = Label("X")
        self["version"] = Label("")
        self["clock"] = Label(time.strftime("%H:%M:%S"))
        self["stationLogo"] = Pixmap()
        self["logoFallback"] = Label("RADIO")
        self["albumArt"] = Pixmap()
        self["artFallback"] = Label("")
        self["station"] = Label("Select a station")
        self["metadata"] = Label("Choose a station from the playlist")
        self._marquee_text = "Choose a station from the playlist"
        self._marquee_pos = 0
        self._marquee_last = 0
        self["streaminfo"] = Label("OK / PLAY starts the selected station")
        self["state"] = Label("READY")

        self["remoteHint"] = Label("")
        self["weatherTitle"] = Label("WEATHER")
        self["weatherHeaderInfo"] = Label("Open-Meteo • Locating... • Updated --:-- • Next --:--")
        self["weatherCurrentIcon"] = Pixmap()
        self["weatherTemp"] = Label("--°C")
        self["weatherTodayRange"] = Label("--° / --°")
        self["weatherCity"] = Label("Locating...")
        self["weatherDetails"] = Label("Weather via current public IP")
        self["weatherExtra"] = Label("")
        for _i in range(1, 4):
            self["weatherDay%d" % _i] = Label("---")
            self["weatherIcon%d" % _i] = Pixmap()
            self["weatherTemp%d" % _i] = Label("-- / --°")
        self["artTitle"] = Label("NOW PLAYING ART")
        self["playlistTitle"] = Label("DG RADIO PLAYLIST")
        self["headNo"] = Label("No.")
        self["headStation"] = Label("Radio Station")
        self["headType"] = Label("Type")
        self["headCodec"] = Label("Codec / Bitrate")
        self["list"] = StationList([])
        self["scrollUp"] = Label("▲")
        self["scrollDown"] = Label("▼")
        self["winampScrollThumb"] = Label("")
        self["winampScrollGrip"] = Label("")
        # No native scrollbar skin attributes: keep this compatible across images.
        self.onLayoutFinish.append(self._updateWinampScroll)

        # MediaPlayerActions catches physical PLAY / PAUSE / STOP / PREVIOUS / NEXT
        # on OpenATV keymaps. DirectionActions catches arrows and CH+/CH-.
        self["actions"] = ActionMap([
            "OkCancelActions", "ColorActions", "DirectionActions",
            "MediaPlayerActions", "InfobarEPGActions", "MenuActions"
        ], {
            "ok": self.playSelected,
            "cancel": self.exitPlugin,
            "red": self.exitPlugin,
            "green": self.playSelected,
            "yellow": self.stopStream,
            "blue": self.openCountrySelector,
            "up": self.moveUp,
            "down": self.moveDown,
            "left": self.previousStation,
            "right": self.nextStation,
            "chplus": self.nextStation,
            "chminus": self.previousStation,
            "play": self.playSelected,
            "pause": self.pauseStream,
            "stop": self.stopStream,
            "previous": self.previousStation,
            "next": self.nextStation,
            "EPGPressed": self.showHelp,
            "menu": self.openSettings,
        }, -2)

        self.timer = eTimer()
        try:
            self.timer.callback.append(self.pollStatus)
        except Exception:
            try:
                self.timer.timeout.connect(self.pollStatus)
            except Exception:
                pass
        self.timer.start(1000, False)

        self.loadStations()
        self._updateCountryUI()
        self._loadWeatherCache()
        self._startWeatherRefresh(force=True)
        self.onClose.append(self.cleanup)
        self._initUpdater(startup=True)
        if config.plugins.dgradioro.autoplay.value and self.stations:
            self.playSelected()

    def createSummary(self):
        if (DGRadioSummary is not None and self.frontpanel_mode != "off"
                and self.frontpanel_caps["profile"] in ("text", "small", "large")):
            return DGRadioSummary
        # Numeric, absent and unknown panels retain the image's default summary.
        return None

    def frontPanelState(self):
        st = self.current_station if self.playing else self.getSelectedStation()
        st = st or {}
        artist = self.fp_artist if self.playing else ""
        title = self.fp_title if self.playing else ""
        status = "PAUSED" if self.paused else ("LIVE" if self.playing else "STOPPED")
        image = None
        if self.playing:
            key = self._artworkKey(artist, title) if artist and title else None
            candidates = []
            if key:
                candidates.append(os.path.join(ARTWORK_CACHE, "%s.jpg" % key))
            station_id = _safe(st.get("id"))
            if station_id:
                candidates.append(self._logoPath(station_id))
            image = next((path for path in candidates if os.path.isfile(path)), None)
        return dict(station=_safe(st.get("name")) or "DG Radio",
                    artist=artist, title=title or (_safe(st.get("category")) if self.playing else ""),
                    status=status, image=image)

    def _countryCode(self):
        code = _safe(config.plugins.dgradioro.country.value).lower()
        if code in COUNTRY_MAP:
            return code
        return COUNTRIES[0]["code"] if COUNTRIES else "ro"

    def _countryInfo(self, code=None):
        code = (code or self._countryCode()).lower()
        info = COUNTRY_MAP.get(code)
        if info:
            return info
        return COUNTRIES[0] if COUNTRIES else {"code": "ro", "name": "Romania", "file": "stations_ro.json", "itunes_country": "RO"}

    def _updateCountryUI(self):
        info = self._countryInfo()
        label = _safe(info.get("name")).upper()
        try:
            self["remoteHint"].setText(label)
            self["playlistTitle"].setText("DG RADIO PLAYLIST  •  %s" % label)
        except Exception:
            pass

    def loadStations(self):
        selected_id = None
        current = self.getSelectedStation()
        if current:
            selected_id = current.get("id")
        info = self._countryInfo()
        station_file = os.path.join(PLUGIN_PATH, _safe(info.get("file")))
        if not os.path.isfile(station_file):
            station_file = STATIONS_FILE
        try:
            with open(station_file, "r") as handle:
                data = json.load(handle)
            self.stations = [x for x in data.get("stations", []) if x.get("stream")]
        except Exception as err:
            self.stations = []
            self.session.open(MessageBox, "Could not load station list:\n%s" % err, MessageBox.TYPE_ERROR)

        current_id = self.current_station.get("id") if self.playing and self.current_station else None
        self["list"].setStations(self.stations, current_id)
        if selected_id:
            for i, st in enumerate(self.stations):
                if st.get("id") == selected_id:
                    self["list"].moveToIndex(i)
                    break
        self._updateCountryUI()
        self.updateSelectedDisplay()

    def reloadStations(self):
        self.loadStations()
        self["state"].setText("RELOADED")

    def openCountrySelector(self):
        choices = []
        active = self._countryCode()
        for item in COUNTRIES:
            prefix = "* " if item["code"] == active else ""
            choices.append((prefix + item["name"], item["code"]))
        if not choices:
            self.session.open(MessageBox, "No country lists available.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(
            self.countrySelected,
            ChoiceBox,
            title="Select country / station list",
            list=choices
        )

    def countrySelected(self, choice):
        if not choice:
            return
        try:
            code = _safe(choice[1]).lower()
        except Exception:
            return
        if code not in COUNTRY_MAP or code == self._countryCode():
            return
        if self.playing:
            self.stopStream()
        config.plugins.dgradioro.country.value = code
        try:
            config.plugins.dgradioro.country.save()
            configfile.save()
        except Exception:
            pass
        self.current_station = None
        self.loadStations()
        self["state"].setText(_safe(self._countryInfo().get("name")).upper())

    def getSelectedIndex(self):
        if not self.stations:
            return 0
        try:
            idx = self["list"].getSelectedIndex()
            return max(0, min(idx, len(self.stations) - 1))
        except Exception:
            return 0

    def getSelectedStation(self):
        if not self.stations:
            return None
        return self.stations[self.getSelectedIndex()]

    def moveUp(self):
        self["list"].up()
        self.updateSelectedDisplay()

    def moveDown(self):
        self["list"].down()
        self.updateSelectedDisplay()

    def previousStation(self):
        if not self.stations:
            return
        idx = (self.getSelectedIndex() - 1) % len(self.stations)
        self["list"].moveToIndex(idx)
        self.updateSelectedDisplay(force=True)
        self.playSelected()

    def nextStation(self):
        if not self.stations:
            return
        idx = (self.getSelectedIndex() + 1) % len(self.stations)
        self["list"].moveToIndex(idx)
        self.updateSelectedDisplay(force=True)
        self.playSelected()

    def _updateWinampScroll(self):
        """Update the retro scrollbar without depending on image-specific skin attributes."""
        try:
            total = len(self.stations)
            selected = self.getSelectedIndex()
            # 479..839, leaving native-styled arrow buttons above and below.
            travel = 360
            offset = int(round(float(selected) * travel / max(1, total - 1))) if total > 1 else 0
            y = 479 + offset
            self["winampScrollThumb"].instance.move(ePoint(1136, y))
            self["winampScrollGrip"].instance.move(ePoint(1140, y + 18))
        except Exception:
            pass

    def updateSelectedDisplay(self, force=False):
        self._updateWinampScroll()
        if self.playing and self.current_station and not force:
            return
        st = self.getSelectedStation()
        if not st:
            self["station"].setText("No stations available")
            self._setNowPlayingText("")
            self["streaminfo"].setText("")
            return
        self["station"].setText(_safe(st.get("name")))
        self._setNowPlayingText(_safe(st.get("category")))
        self["streaminfo"].setText("%s  |  %s" % (_safe(st.get("group")), _codec_text(st)))
        self.setStationLogo(st)

    def _resolveStreamUrl(self, url):
        raw = _safe(url).strip()
        if not raw:
            return raw
        clean = raw.split("?", 1)[0].lower()
        if not (clean.endswith(".m3u") or clean.endswith(".pls")):
            return raw
        try:
            req = urllib.request.Request(raw, headers={"User-Agent": "Mozilla/5.0 DG-Radio/0.2 Enigma2"})
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read(65536)
                base = response.geturl()
            text = body.decode("utf-8", "replace")
            if clean.endswith(".pls") or text.lstrip().lower().startswith("[playlist]"):
                for line in text.splitlines():
                    if line.lower().startswith("file") and "=" in line:
                        candidate = line.split("=", 1)[1].strip()
                        if candidate:
                            return urllib.parse.urljoin(base, candidate)
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return urllib.parse.urljoin(base, line)
        except Exception as err:
            print("[DGRadio] Playlist resolve failed for %s: %s" % (raw, err))
        return raw

    def playSelected(self):
        st = self.getSelectedStation()
        if not st:
            return
        url = _safe(st.get("stream"))
        if not url:
            return
        url = self._resolveStreamUrl(url)
        try:
            ref = eServiceReference(4097, 0, url)
            try:
                ref.setName(_safe(st.get("name")))
            except Exception:
                pass
            self.session.nav.playService(ref)
            self.fp_artist = self.fp_title = ""
            self.current_station = st
            self.current_index = self.getSelectedIndex()
            selected_index = self.current_index
            self["list"].setStations(self.stations, st.get("id"))
            self["list"].moveToIndex(selected_index)
            self.started_at = time.time()
            self.playing = True
            self.paused = False
            self["state"].setText("PLAYING")
            self["station"].setText(_safe(st.get("name")))
            self._setNowPlayingText("Connecting to live stream...")
            self["streaminfo"].setText("%s  |  %s  |  LIVE" % (_safe(st.get("group")), _codec_text(st)))
            self.setStationLogo(st)
            self.last_nowplaying_key = None
            self.clearAlbumArtwork(show_station_fallback=True)
        except Exception as err:
            self.playing = False
            self["state"].setText("ERROR")
            self.session.open(MessageBox, "Could not play station:\n%s" % err, MessageBox.TYPE_ERROR)

    def stopStream(self):
        try:
            self.session.nav.stopService()
        except Exception:
            pass
        self.playing = False
        self.paused = False
        self.started_at = None
        selected_index = self.getSelectedIndex()
        self["list"].setStations(self.stations, None)
        self["list"].moveToIndex(selected_index)
        self["state"].setText("STOPPED")
        self.last_nowplaying_key = None
        self.clearAlbumArtwork(show_station_fallback=True)
        self.updateSelectedDisplay(force=True)

    def pauseStream(self):
        # A live radio stream cannot be reliably timeshift-paused on all images.
        # PAUSE therefore stops the live stream; PLAY resumes the live station.
        if self.playing:
            self.stopStream()
            self.paused = True
            self["state"].setText("PAUSED")
        else:
            self.playSelected()

    def _setNowPlayingText(self, value):
        value = _safe(value).replace("\n", " ").strip()
        if value != self._marquee_text:
            self._marquee_text = value
            self._marquee_pos = 0
            self._marquee_last = 0
            self._tickNowPlayingMarquee(force=True)

    def _tickNowPlayingMarquee(self, force=False):
        # Character-based marquee: no custom widgets or dependencies.
        # Static short captions never scroll; long text shows a readable pause.
        text = self._marquee_text
        window = 28
        if len(text) <= window:
            if force:
                self["metadata"].setText(text)
            return
        now = time.time()
        if not force and now - self._marquee_last < 1.0:
            return
        self._marquee_last = now
        padded = text + "     " + text[:window]
        pos = self._marquee_pos
        self["metadata"].setText(padded[pos:pos + window])
        self._marquee_pos = (pos + 1) % (len(text) + 5)

    def pollStatus(self):
        self["clock"].setText(time.strftime("%H:%M:%S"))
        self._tickNowPlayingMarquee()
        self._processPendingLogo()
        self._processPendingArtwork()
        self._processPendingWeather()
        if time.time() - self.weather_last_request >= WEATHER_REFRESH:
            self._startWeatherRefresh()
        if not self.playing or not self.current_station:
            return

        title = ""
        artist = ""
        try:
            service = self.session.nav.getCurrentService()
            info = service and service.info()
            if info:
                try:
                    title = info.getInfoString(iServiceInformation.sTagTitle) or ""
                except Exception:
                    title = ""
                try:
                    artist = info.getInfoString(iServiceInformation.sTagArtist) or ""
                except Exception:
                    artist = ""
        except Exception:
            pass

        display_artist, display_title = self._splitNowPlaying(artist, title)
        self.fp_artist, self.fp_title = display_artist, display_title
        if display_artist and display_title:
            now = "%s - %s" % (display_artist, display_title)
        else:
            now = title or artist
        if now:
            self._setNowPlayingText(now[:120])
        else:
            self._setNowPlayingText(_safe(self.current_station.get("category")))

        if display_artist and display_title:
            key = self._artworkKey(display_artist, display_title)
            if key and key != self.last_nowplaying_key:
                self.last_nowplaying_key = key
                self.setAlbumArtwork(display_artist, display_title)
        elif self.last_nowplaying_key is not None:
            self.last_nowplaying_key = None
            self.clearAlbumArtwork(show_station_fallback=True)
        elif not self.showing_station_fallback:
            self.showStationArtworkFallback()

    def _logoPath(self, station_id):
        """Persistent logo cache, separated by country and station."""
        key = self._countryCode() + "_" + re.sub(r"[^a-zA-Z0-9_-]", "_", _safe(station_id))
        try:
            if not os.path.isdir(LOGO_CACHE):
                os.makedirs(LOGO_CACHE)
        except Exception as err:
            print("[DGRadio] Cannot create logo cache: %s" % err)
        return os.path.join(LOGO_CACHE, "%s.img" % key)

    def _validLogo(self, path):
        """Reject HTML error pages and partial files masquerading as images."""
        try:
            size = os.path.getsize(path)
            if not 256 < size <= 1024 * 1024:
                return False
            with open(path, "rb") as handle:
                head = handle.read(32)
            return (head.startswith(b"\x89PNG\r\n\x1a\n") or
                    head.startswith(b"\xff\xd8\xff") or
                    (head.startswith(b"RIFF") and head[8:12] == b"WEBP") or
                    head.startswith((b"GIF87a", b"GIF89a")))
        except Exception:
            return False

    def setStationLogo(self, station):
        station_id = _safe((station or {}).get("id"))
        if not station_id:
            return
        self.logo_current_id = (self._countryCode(), station_id)
        try:
            self["stationLogo"].hide()
        except Exception:
            pass
        path = self._logoPath(station_id)
        if self._validLogo(path):
            self["logoFallback"].setText("")
            self._decodeLogo(path)
            return
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
        # Never leave an empty or misleading old logo while fetching a new one.
        self["logoFallback"].setText("DG RADIO")
        self._decodeLogo(FALLBACK_LOGO, fallback=True)
        url = _safe((station or {}).get("logo")).strip() or STATION_LOGOS.get(station_id)
        if not url:
            return
        key = self.logo_current_id
        if key in self.logo_loading:
            return
        self.logo_loading.add(key)
        threading.Thread(target=self._downloadLogo, args=(key, url, path), daemon=True).start()

    def _downloadLogo(self, key, url, path):
        ok = False
        tmp = path + ".tmp"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DG-Radio/0.2 Enigma2", "Accept": "image/png,image/jpeg,image/webp,image/gif,*/*;q=0.5"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read(1024 * 1024 + 1)
            if 256 < len(data) <= 1024 * 1024:
                with open(tmp, "wb") as handle:
                    handle.write(data)
                if self._validLogo(tmp):
                    os.replace(tmp, path)
                    ok = True
                else:
                    print("[DGRadio] Rejected non-image logo: %s" % (key,))
        except Exception as err:
            print("[DGRadio] Logo download failed for %s: %s" % (key, err))
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            self.logo_loading.discard(key)
        self.logo_pending = (key, path if ok else None)

    def _processPendingLogo(self):
        pending = self.logo_pending
        if not pending:
            return
        self.logo_pending = None
        key, path = pending
        if key != self.logo_current_id:
            return
        if path and self._validLogo(path):
            self._decodeLogo(path)
            if not self.last_nowplaying_key or self.showing_station_fallback:
                self.showStationArtworkFallback()
        else:
            self["logoFallback"].setText("DG RADIO")
            self._decodeLogo(FALLBACK_LOGO, fallback=True)

    def _decodeLogo(self, path, fallback=False):
        try:
            if not path or not os.path.isfile(path):
                if not fallback and os.path.isfile(FALLBACK_LOGO):
                    return self._decodeLogo(FALLBACK_LOGO, fallback=True)
                self["logoFallback"].setText("DG RADIO")
                return
            self.picload.setPara((145, 84, 1, 1, False, 1, "#00000000"))
            result = self.picload.startDecode(path)
            if result is not None and result != 0:
                raise ValueError("ePicLoad.startDecode returned %s" % result)
        except Exception as err:
            print("[DGRadio] Logo decode failed: %s" % err)
            if not fallback and os.path.isfile(FALLBACK_LOGO):
                self._decodeLogo(FALLBACK_LOGO, fallback=True)
            else:
                self["logoFallback"].setText("DG RADIO")

    def _logoDecoded(self, picInfo=None):
        try:
            ptr = self.picload.getData()
            if ptr is not None and self["stationLogo"].instance is not None:
                self["stationLogo"].instance.setPixmap(ptr)
                self["stationLogo"].show()
                self["logoFallback"].setText("")
            else:
                self["logoFallback"].setText("DG RADIO")
        except Exception as err:
            print("[DGRadio] Logo display failed: %s" % err)
            self["logoFallback"].setText("DG RADIO")

    def _compactText(self, value):
        value = _safe(value).strip().lower()
        try:
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
        except Exception:
            pass
        return re.sub(r"[^a-z0-9]+", "", value)

    def _looksLikeStationName(self, value):
        compact = self._compactText(value)
        if not compact:
            return False
        st = self.current_station or {}
        candidates = [st.get("name"), st.get("id")]
        for candidate in candidates:
            c = self._compactText(candidate)
            if c and (compact == c or compact in c or c in compact):
                return True
        # Common station-style prefixes found in ICY metadata.
        station_words = ("radio", "fm", "live", "stream")
        low = _safe(value).lower()
        return any(word in low for word in station_words) and len(compact) <= 24

    def _splitNowPlaying(self, artist, title):
        artist = _safe(artist).strip()
        title = _safe(title).strip()

        # German station metadata is often emitted as:
        #   "Major Tom (Völlig Losgelöst)" von Peter Schilling
        # Parse this before the generic "Artist - Title" rules.
        for candidate in (title, artist):
            if not candidate:
                continue
            match = re.match(r"^\s*[\"'„“”]?(.+?)[\"'„“”]?\s+von\s+(.+?)\s*$", candidate, re.I | re.U)
            if match:
                song = match.group(1).strip().strip("\"'„“” ")
                performer = match.group(2).strip().strip("\"'„“” ")
                if song and performer:
                    return performer, song

        # Some streams expose the station name as the ICY artist and put the
        # real "Artist - Song" in the title, e.g.:
        #   artist = "MagicFM"
        #   title  = "Tina Turner - Private Dancer"
        if artist and title and self._looksLikeStationName(artist):
            parts = [x.strip() for x in re.split(r"\s[-–—]\s", title) if x.strip()]
            if len(parts) >= 2:
                return parts[0], " - ".join(parts[1:])

        if artist and title:
            return artist, title

        combined = title or artist
        if not combined:
            return "", ""

        parts = [x.strip() for x in re.split(r"\s[-–—]\s", combined) if x.strip()]
        if len(parts) < 2:
            return "", ""

        # Many stations prepend their own name to the actual metadata:
        #   "MagicFM - Tina Turner - Private Dancer"
        # Strip that prefix before searching artwork.
        if len(parts) >= 3 and self._looksLikeStationName(parts[0]):
            return parts[1], " - ".join(parts[2:])

        left = parts[0]
        right = " - ".join(parts[1:])
        if not left or not right:
            return "", ""

        # Avoid obvious slogans / generic stream labels.
        generic = (" live", "radio ", " fm", "stream", "hit radio", "live!", "online")
        low_left = " " + left.lower()
        low_right = " " + right.lower()
        if any(x in low_left for x in generic) or any(x in low_right for x in generic):
            return "", ""
        if left.startswith("#") or right.startswith("#"):
            return "", ""
        return left, right

    def _artworkKey(self, artist, title):
        value = ("%s|%s" % (_safe(artist), _safe(title))).strip().lower()
        if not value.strip("|"):
            return None
        return hashlib.sha1(value.encode("utf-8", "ignore")).hexdigest()[:20]

    def _artworkPath(self, key):
        try:
            if not os.path.isdir(ARTWORK_CACHE):
                os.makedirs(ARTWORK_CACHE)
        except Exception:
            pass
        return os.path.join(ARTWORK_CACHE, "%s.jpg" % key)

    def clearAlbumArtwork(self, show_station_fallback=True):
        self.artwork_current_key = None
        try:
            self["albumArt"].hide()
        except Exception:
            pass
        self["artFallback"].setText("")
        self.showing_station_fallback = False
        if show_station_fallback:
            self.showStationArtworkFallback()

    def showStationArtworkFallback(self):
        """Fill the NOW PLAYING ART frame with the current station logo.

        This is the permanent fallback when there is no song artwork, while
        metadata changes, or when an artwork lookup fails.
        """
        st = self.current_station if self.current_station else self.getSelectedStation()
        station_id = _safe((st or {}).get("id"))
        if not station_id:
            return
        path = self._logoPath(station_id)
        if self._validLogo(path):
            try:
                self.showing_station_fallback = True
                self.artwork_current_key = "station:%s" % station_id
                self.artload.setPara((345, 270, 1, 1, False, 1, "#00000000"))
                self.artload.startDecode(path)
                self["artFallback"].setText("")
                return
            except Exception as err:
                print("[DGRadio] Station fallback decode failed: %s" % err)
        # If there is no usable station logo, use the DG Radio application icon.
        if os.path.isfile(FALLBACK_ART):
            try:
                self.showing_station_fallback = True
                self.artwork_current_key = "station:%s" % station_id
                self.artload.setPara((345, 270, 1, 1, False, 1, "#00000000"))
                self.artload.startDecode(FALLBACK_ART)
                self["artFallback"].setText("")
                return
            except Exception as err:
                print("[DGRadio] App icon fallback decode failed: %s" % err)
        self["artFallback"].setText("DG RADIO")

    def setAlbumArtwork(self, artist, title):
        key = self._artworkKey(artist, title)
        if not key:
            self.clearAlbumArtwork(show_station_fallback=True)
            return
        self.artwork_current_key = key
        self.showing_station_fallback = False
        path = self._artworkPath(key)
        if os.path.isfile(path) and os.path.getsize(path) > 512:
            self._decodeArtwork(path)
            return
        if key in self.artwork_miss:
            self.showStationArtworkFallback()
            return
        # Keep station logo visible while the search runs, avoiding a black frame.
        self.showStationArtworkFallback()
        self.artwork_current_key = key
        self.showing_station_fallback = True
        if key in self.artwork_loading:
            return
        self.artwork_loading.add(key)
        threading.Thread(target=self._findArtwork, args=(key, artist, title, path), daemon=True).start()

    def _cleanArtworkQueryText(self, value):
        value = _safe(value)
        # Remove common radio decorations that reduce search quality.
        value = re.sub(r"\[[^\]]+\]", " ", value)
        value = re.sub(r"\([^)]*(?:new music|official|radio edit)[^)]*\)", " ", value, flags=re.I)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _itunesSearch(self, artist, title, country="RO"):
        query = "%s %s" % (self._cleanArtworkQueryText(artist), self._cleanArtworkQueryText(title))
        params = urllib.parse.urlencode({
            "term": query.strip(),
            "media": "music",
            "entity": "song",
            "limit": 15,
            "country": country,
        })
        url = "https://itunes.apple.com/search?" + params
        req = urllib.request.Request(url, headers={"User-Agent": "DG-Radio/0.2 Enigma2"})
        with urllib.request.urlopen(req, timeout=7) as response:
            payload = response.read(768 * 1024)
        data = json.loads(payload.decode("utf-8", "ignore"))
        return data.get("results", [])

    def _findArtwork(self, key, artist, title, path):
        ok = False
        try:
            artwork_url = None
            # Search the active country's catalog first, then the broader US catalog.
            primary_country = _safe(self._countryInfo().get("itunes_country")) or self._countryCode().upper()
            for country in (primary_country, "US"):
                try:
                    results = self._itunesSearch(artist, title, country)
                    artwork_url = self._chooseArtwork(results, artist, title)
                    if artwork_url:
                        break
                except Exception as err:
                    print("[DGRadio] Artwork search %s failed: %s" % (country, err))

            if artwork_url:
                # iTunes artwork URLs commonly support larger square variants.
                artwork_url = re.sub(r"100x100[^./]*", "600x600bb", artwork_url)
                req = urllib.request.Request(artwork_url, headers={"User-Agent": "DG-Radio/0.2 Enigma2"})
                with urllib.request.urlopen(req, timeout=8) as response:
                    image = response.read(2 * 1024 * 1024)
                if len(image) > 512:
                    tmp = path + ".tmp"
                    with open(tmp, "wb") as handle:
                        handle.write(image)
                    os.rename(tmp, path)
                    ok = True
        except Exception as err:
            print("[DGRadio] Artwork lookup failed for %s - %s: %s" % (artist, title, err))
        try:
            self.artwork_loading.discard(key)
        except Exception:
            pass
        if not ok:
            self.artwork_miss.add(key)
        self.artwork_pending = (key, path if ok else None)

    def _normText(self, value):
        value = _safe(value).lower()
        try:
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
        except Exception:
            pass
        value = re.sub(r"\[[^\]]+\]", " ", value)
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return set(x for x in value.split() if len(x) > 1)

    def _chooseArtwork(self, results, artist, title):
        want_artist = self._normText(artist)
        want_title = self._normText(title)
        best_url = None
        best_score = -1
        for item in results or []:
            url = item.get("artworkUrl100")
            if not url:
                continue
            got_artist = self._normText(item.get("artistName"))
            got_title = self._normText(item.get("trackName"))
            artist_hits = len(want_artist & got_artist)
            title_hits = len(want_title & got_title)
            score = artist_hits * 5 + title_hits * 6
            # Prefer results that match both sides when both are available.
            if want_artist and artist_hits == 0:
                score -= 4
            if want_title and title_hits == 0:
                score -= 5
            if score > best_score:
                best_score = score
                best_url = url
        return best_url if best_score >= 5 else None

    def _processPendingArtwork(self):
        pending = self.artwork_pending
        if not pending:
            return
        self.artwork_pending = None
        key, path = pending
        if key != self.artwork_current_key:
            return
        if path and os.path.isfile(path):
            self._decodeArtwork(path)
        else:
            self.showStationArtworkFallback()

    def _decodeArtwork(self, path):
        try:
            self.artload.setPara((345, 270, 1, 1, False, 1, "#00000000"))
            self.artload.startDecode(path)
        except Exception as err:
            print("[DGRadio] Artwork decode failed: %s" % err)

    def _artDecoded(self, picInfo=None):
        try:
            ptr = self.artload.getData()
            if ptr is not None and self["albumArt"].instance is not None:
                self["albumArt"].instance.setPixmap(ptr)
                self["albumArt"].show()
                self["artFallback"].setText("")
                self.showing_station_fallback = str(self.artwork_current_key).startswith("station:")
        except Exception as err:
            print("[DGRadio] Artwork display failed: %s" % err)

    def _loadWeatherCache(self):
        try:
            if os.path.isfile(WEATHER_CACHE):
                with open(WEATHER_CACHE, "r") as handle:
                    cached = json.load(handle)
                if cached and time.time() - float(cached.get("fetched_at", 0)) < 7200:
                    self.weather_data = cached
                    self._applyWeather(cached)
        except Exception as err:
            print("[DGRadio] Weather cache load failed: %s" % err)

    def _startWeatherRefresh(self, force=False):
        if self.weather_loading:
            return
        now = time.time()
        if not force and now - self.weather_last_request < WEATHER_REFRESH:
            return
        self.weather_last_request = now
        self.weather_loading = True
        threading.Thread(target=self._weatherWorker, daemon=True).start()

    def _jsonRequest(self, url, timeout=7):
        req = urllib.request.Request(url, headers={"User-Agent": "DG-Radio/0.2 Enigma2"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read(1024 * 1024)
        return json.loads(payload.decode("utf-8", "ignore"))

    def _ipLocation(self):
        # Public-IP geolocation: intentionally independent from the configured
        # OAWeather city, so the receiver follows the internet exit location.
        try:
            data = self._jsonRequest("https://ipapi.co/json/", 6)
            lat = data.get("latitude")
            lon = data.get("longitude")
            city = data.get("city") or data.get("region") or "Current location"
            if lat is not None and lon is not None:
                return city, float(lat), float(lon)
        except Exception as err:
            print("[DGRadio] ipapi location failed: %s" % err)
        try:
            data = self._jsonRequest("https://ipwho.is/", 6)
            if data.get("success", True):
                lat = data.get("latitude")
                lon = data.get("longitude")
                city = data.get("city") or data.get("region") or "Current location"
                if lat is not None and lon is not None:
                    return city, float(lat), float(lon)
        except Exception as err:
            print("[DGRadio] ipwho location failed: %s" % err)
        return None

    def _weatherWorker(self):
        result = None
        try:
            location = self._ipLocation()
            if not location:
                raise RuntimeError("Could not determine public-IP location")
            city, lat, lon = location
            params = urllib.parse.urlencode({
                "latitude": "%.5f" % lat,
                "longitude": "%.5f" % lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 4,
            })
            data = self._jsonRequest("https://api.open-meteo.com/v1/forecast?" + params, 8)
            current = data.get("current", {})
            daily = data.get("daily", {})
            days = []
            times = daily.get("time", [])
            codes = daily.get("weather_code", [])
            highs = daily.get("temperature_2m_max", [])
            lows = daily.get("temperature_2m_min", [])
            for idx in range(1, min(4, len(times))):
                days.append({
                    "date": times[idx],
                    "code": codes[idx] if idx < len(codes) else None,
                    "max": highs[idx] if idx < len(highs) else None,
                    "min": lows[idx] if idx < len(lows) else None,
                })
            today = {
                "max": highs[0] if len(highs) > 0 else None,
                "min": lows[0] if len(lows) > 0 else None,
            }
            result = {
                "fetched_at": time.time(),
                "city": city,
                "lat": lat,
                "lon": lon,
                "current": current,
                "today": today,
                "days": days,
            }
            try:
                with open(WEATHER_CACHE + ".tmp", "w") as handle:
                    json.dump(result, handle)
                os.rename(WEATHER_CACHE + ".tmp", WEATHER_CACHE)
            except Exception:
                pass
        except Exception as err:
            print("[DGRadio] Weather refresh failed: %s" % err)
        self.weather_pending = result
        self.weather_loading = False

    def _processPendingWeather(self):
        pending = self.weather_pending
        if pending is None:
            return
        self.weather_pending = None
        if pending:
            self.weather_data = pending
            self._applyWeather(pending)
        elif not self.weather_data:
            self["weatherCity"].setText("Weather unavailable")
            self["weatherDetails"].setText("Check internet connection")
            self["weatherExtra"].setText("")

    def _weatherCondition(self, code):
        try:
            code = int(code)
        except Exception:
            return "Weather"
        if code == 0:
            return "Clear"
        if code in (1, 2):
            return "Partly cloudy"
        if code == 3:
            return "Cloudy"
        if code in (45, 48):
            return "Fog"
        if code in (51, 53, 55, 56, 57):
            return "Drizzle"
        if code in (61, 63, 65, 66, 67, 80, 81, 82):
            return "Rain"
        if code in (71, 73, 75, 77, 85, 86):
            return "Snow"
        if code in (95, 96, 99):
            return "Thunderstorm"
        return "Weather"

    def _weatherYahooCode(self, code):
        try:
            code = int(code)
        except Exception:
            return "na"
        if code == 0:
            return "32"
        if code == 1:
            return "34"
        if code == 2:
            return "30"
        if code == 3:
            return "26"
        if code in (45, 48):
            return "20"
        if code in (51, 53, 55):
            return "9"
        if code in (56, 57, 66, 67):
            return "8"
        if code in (61, 63, 65):
            return "12"
        if code in (71, 73, 75, 77):
            return "16"
        if code in (80, 81, 82):
            return "39"
        if code in (85, 86):
            return "46"
        if code in (95, 96, 99):
            return "4"
        return "na"

    def _setWeatherIcon(self, widget, code):
        try:
            icon = os.path.join(OAWEATHER_ICON_PATH, "%s.png" % self._weatherYahooCode(code))
            if not os.path.isfile(icon):
                icon = os.path.join(OAWEATHER_ICON_PATH, "na.png")
            pix = LoadPixmap(icon) if os.path.isfile(icon) else None
            if pix is not None and self[widget].instance is not None:
                self[widget].instance.setPixmap(pix)
                self[widget].show()
        except Exception as err:
            print("[DGRadio] Weather icon failed: %s" % err)

    def _cardinal(self, degrees):
        try:
            deg = float(degrees) % 360
            names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
            return names[int((deg + 22.5) / 45.0) % 8]
        except Exception:
            return ""

    def _fmtTemp(self, value):
        try:
            return "%d°" % int(round(float(value)))
        except Exception:
            return "--°"

    def _applyWeather(self, data):
        try:
            current = data.get("current", {})
            city = _safe(data.get("city")) or "Current location"
            temp = current.get("temperature_2m")
            humidity = current.get("relative_humidity_2m")
            wind = current.get("wind_speed_10m")
            direction = self._cardinal(current.get("wind_direction_10m"))
            condition = self._weatherCondition(current.get("weather_code"))
            self["weatherTemp"].setText(self._fmtTemp(temp) + "C")
            today = data.get("today", {})
            self["weatherTodayRange"].setText("%s / %s" % (
                self._fmtTemp(today.get("max")), self._fmtTemp(today.get("min"))
            ))
            self["weatherCity"].setText(city[:24])
            self["weatherDetails"].setText(condition[:24])
            extra = "%s km/h %s  •  %s%%" % (
                int(round(float(wind))) if wind is not None else "--",
                direction,
                int(round(float(humidity))) if humidity is not None else "--",
            )
            self["weatherExtra"].setText(extra[:28])
            fetched = float(data.get("fetched_at", 0) or 0)
            updated = time.strftime("%H:%M", time.localtime(fetched)) if fetched else "--:--"
            next_ts = fetched + WEATHER_REFRESH if fetched else 0
            next_update = time.strftime("%H:%M", time.localtime(next_ts)) if next_ts else "--:--"
            self["weatherHeaderInfo"].setText("Open-Meteo • %s • Updated %s • Next %s" % (city[:18], updated, next_update))
            self._setWeatherIcon("weatherCurrentIcon", current.get("weather_code"))

            days = data.get("days", [])
            for i in range(1, 4):
                item = days[i - 1] if i - 1 < len(days) else {}
                date = _safe(item.get("date"))
                try:
                    label = time.strftime("%a", time.strptime(date, "%Y-%m-%d")).upper()
                except Exception:
                    label = "---"
                self["weatherDay%d" % i].setText(label)
                self["weatherTemp%d" % i].setText("%s / %s" % (self._fmtTemp(item.get("max")), self._fmtTemp(item.get("min"))))
                self._setWeatherIcon("weatherIcon%d" % i, item.get("code"))
        except Exception as err:
            print("[DGRadio] Weather display failed: %s" % err)

    def showHelp(self):
        st = self.current_station if self.playing and self.current_station else self.getSelectedStation()
        if not st:
            return
        txt = (
            "%s\n\n"
            "Type: %s\n"
            "Category: %s\n"
            "Codec / Bitrate: %s\n\n"
            "Stream:\n%s\n\n"
            "HELP / STATION DETAILS\n\n"
            "Remote controls:\n"
            "OK / PLAY = Play selected station\n"
            "STOP = Stop\n"
            "PAUSE = Pause / resume live\n"
            "PREV / NEXT = Change station\n"
            "UP / DOWN = Browse playlist\n"
            "LEFT / RIGHT = Previous / next station\n"
            "CH+ / CH- = Next / previous station\n"
            "EPG = Help / station details\n"
            "MENU = Settings\n"
            "BLUE = Select country / station list\n"
            "RED / EXIT = Close plugin\n\n"
            "Weather:\n"
            "OAWeather must be installed for the WEATHER frame to work correctly.\n"
            "Weather data is provided by Open-Meteo; location is detected from the public IP."
        ) % (
            _safe(st.get("name")), _safe(st.get("group")), _safe(st.get("category")),
            _codec_text(st), _safe(st.get("stream"))
        )
        self.session.open(MessageBox, txt, MessageBox.TYPE_INFO, timeout=0)

    def openSettings(self):
        self.session.openWithCallback(self.settingsClosed, DGSettings)

    def settingsClosed(self, *args):
        self.loadStations()
        self._updateCountryUI()

    def exitPlugin(self):
        self.close()

    def cleanup(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        if config.plugins.dgradioro.restore_service.value and self.old_service:
            try:
                self.session.nav.playService(self.old_service)
            except Exception:
                pass
        else:
            try:
                if self.playing:
                    self.session.nav.stopService()
            except Exception:
                pass


def main(session, **kwargs):
    session.open(DGRadio)


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="Internet radio, the Winamp way! Multi-country stations, album art, live track info and weather.",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            needsRestart=False,
            fnc=main,
        )
    ]
