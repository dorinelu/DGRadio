# -*- coding: utf-8 -*-
"""Adaptive, session-owned Enigma2 summary. No direct device writes or downloads."""
import os
import time
from xml.sax.saxutils import escape

from enigma import getDesktop, eTimer, ePicLoad
from Screens.Screen import Screen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText


def box_value(key, default=None):
    try:
        from Components.SystemInfo import BoxInfo
        value = BoxInfo.getItem(key)
        if value is not None:
            return value
    except Exception:
        pass
    try:
        from Components.SystemInfo import SystemInfo
        return SystemInfo.get(key, default)
    except Exception:
        return default


def detect():
    kind = str(box_value('displaytype', '') or '').lower()
    model = str(box_value('model', '') or box_value('machinebuild', '') or 'unknown')
    width = height = 0
    try:
        size = getDesktop(1).size()
        width, height = size.width(), size.height()
    except Exception:
        pass
    present = False
    try:
        from enigma import eDBoxLCD
        lcd = eDBoxLCD.getInstance()
        present = bool(lcd and lcd.detected())
    except Exception:
        pass
    present = present or bool(box_value('FrontpanelDisplay', False)) or bool(box_value('GraphicLCD', False))
    profile = 'none'
    if kind in ('7segment', '7-segment', 'led'):
        profile = 'numeric'
    elif kind in ('textlcd', 'text', 'vfd'):
        profile = 'text'
    elif kind not in ('none', 'nodisplay') and (present or kind in ('lcd', 'oled', 'graphic', 'colorlcd')):
        if 32 <= width <= 1920 and 16 <= height <= 1080:
            profile = 'large' if width >= 240 and height >= 128 else 'small'
    return dict(model=model, type=kind or 'unknown', profile=profile, width=width, height=height)


def describe(caps):
    return '%s | %s | %sx%s | %s' % (caps['model'], caps['type'], caps['width'], caps['height'], caps['profile'])


def clean(value):
    return ' '.join(str(value or '').split())[:240]


def page_text(text, width, tick):
    """Readable pages, rather than a dependency on image-specific scroll renderers."""
    text = clean(text)
    if len(text) <= width:
        return text
    pages = [text[i:i + width] for i in range(0, len(text), width)]
    return pages[(tick // 4) % len(pages)]


def make_skin(caps):
    w, h = caps['width'], caps['height']
    if caps['profile'] == 'text':
        # Text front panels use the standard Enigma2 Label renderer / driver.
        return '<screen name="DGRadioSummary" position="0,0" size="%d,%d"><widget source="panelText" render="Label" position="0,0" size="%d,%d" font="Regular;12" /></screen>' % (max(1,w), max(1,h), max(1,w), max(1,h)), 0
    if h < 48:
        font = max(8, min(h-2, w//8))
        return ('<screen name="DGRadioSummary" position="0,0" size="%d,%d" backgroundColor="#000000">'
                '<widget name="station" position="0,0" size="%d,%d" font="Regular;%d" foregroundColor="#FFFFFF" backgroundColor="#000000" valign="center" />'
                '</screen>') % (w,h,w,h,font), 0
    margin = max(1, min(w, h) // 40)
    line = max(1, h // 5)
    font = max(8, min(line - 2, w // 12))
    art = min(h - 2*line - 3*margin, w // 3) if caps['profile'] == 'large' else 0
    left = art + 2*margin if art else margin
    body_width = w - left - margin
    parts = ['<screen name="DGRadioSummary" position="0,0" size="%d,%d" backgroundColor="#000000">' % (w,h)]
    def label(name, x, y, ww, hh, ff):
        parts.append('<widget name="%s" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#FFFFFF" backgroundColor="#000000" valign="center" />' % (escape(name), x,y,ww,hh,ff))
    label('station', margin, margin, w-2*margin, line, font)
    label('artist', left, line+margin, body_width, line, font)
    label('track', left, 2*line+margin, body_width, 2*line-margin, font)
    label('status', margin, h-line, w-2*margin, line, max(8,font-2))
    if art:
        parts.append('<widget name="art" position="%d,%d" size="%d,%d" alphatest="on" />' % (margin,line+margin,art,art))
    parts.append('</screen>')
    return ''.join(parts), art


class DGRadioSummary(Screen):
    def __init__(self, session, parent):
        Screen.__init__(self, session, parent=parent)
        self.radio = parent
        self.caps = dict(parent.frontpanel_caps)
        self.skin, self.art_size = make_skin(self.caps)
        # Do not let a generic external Summary skin replace adaptive geometry.
        self.skinName = 'DGRadioAdaptiveSummary'
        self['panelText'] = StaticText('DG Radio')
        for name in ('station', 'artist', 'track', 'status'):
            self[name] = Label('')
        self['art'] = Pixmap()
        self.tick = 0
        self.last_content = None
        self.active = False
        self.closed = False
        self.requested_path = None
        self.decoding_path = None
        self.shown_path = None
        self.failed_path = None
        self.decoder = ePicLoad()
        self.connections = []
        try:
            self.decoder.PictureData.get().append(self.picture_ready)
        except Exception:
            self.connections.append(self.decoder.PictureData.connect(self.picture_ready))
        self.timer = eTimer()
        try:
            self.timer.callback.append(self.refresh)
        except Exception:
            self.connections.append(self.timer.timeout.connect(self.refresh))
        self.onShow.append(self.start)
        self.onHide.append(self.stop)
        self.onClose.append(self.shutdown)

    def start(self):
        if self.closed:
            return
        self.active = True
        self.refresh()
        self.timer.start(1000, False)

    def stop(self):
        self.active = False
        self.timer.stop()

    def shutdown(self):
        self.stop()
        self.closed = True
        self.requested_path = None
        self.radio = None

    def refresh(self):
        if not self.active or self.closed:
            return
        try:
            state = self.radio.frontPanelState()
            content = (state['station'], state['artist'], state['title'], state['status'])
            if content != self.last_content:
                self.tick = 0
                self.last_content = content
            station, artist, title, status = content
            mode = self.radio.frontpanel_mode
            if mode == 'station':
                artist = title = ''
            clock = time.strftime('%H:%M')
            if self.caps['profile'] == 'text':
                # Full strings let the image/driver apply its own VFD scrolling.
                text = station
                if mode != 'station' and (self.tick // 8) % 2:
                    text = ' - '.join(x for x in (artist,title) if x) or status
                if status in ('STOPPED', 'PAUSED', 'ERROR'):
                    text = status if (self.tick // 4) % 2 else station
                self['panelText'].setText(text)
            elif self.caps['height'] < 48:
                text = station
                if mode != 'station' and (self.tick // 12) % 2:
                    text = ' - '.join(x for x in (artist,title) if x) or status
                font = max(8, min(self.caps['height']-2, self.caps['width']//8))
                chars = max(4, int(self.caps['width']/(font*0.65)))
                self['station'].setText(page_text(text, chars, self.tick))
            else:
                font = max(8, min(self.caps['height']//5-2, self.caps['width']//12))
                chars = max(4, int((self.caps['width']-4)/(font*0.65)))
                body_chars = max(4, int((self.caps['width']-self.art_size-6)/(font*0.65)))
                self['station'].setText(page_text(station, chars, self.tick))
                self['artist'].setText(page_text(artist, body_chars, self.tick))
                self['track'].setText(page_text(title, body_chars, self.tick))
                self['status'].setText('%s  %s' % (status,clock))
                path = state['image'] if mode in ('auto', 'full') else None
                self.set_image(path)
            self.tick += 1
        except Exception as err:
            # A front-panel failure must not affect radio playback.
            print('[DGRadio] Front panel disabled for this session: %s' % err)
            self.stop()

    def set_image(self, path):
        if not self.art_size:
            return
        if path != self.requested_path:
            self.requested_path = path
            self.failed_path = None
            self.shown_path = None
            self['art'].hide()
        if path and path not in (self.shown_path, self.failed_path) and self.decoding_path is None:
            self.decoding_path = path
            try:
                self.decoder.setPara((self.art_size,self.art_size,1,1,False,1,'#00000000'))
                result = self.decoder.startDecode(path)
                if result not in (None, 0):
                    self.failed_path = path
                    self.decoding_path = None
            except Exception:
                self.failed_path = path
                self.decoding_path = None

    def picture_ready(self, *args):
        path = self.decoding_path
        self.decoding_path = None
        if self.closed or not self.active or path != self.requested_path:
            return
        try:
            data = self.decoder.getData()
            if data is not None and self['art'].instance is not None:
                self['art'].instance.setPixmap(data)
                self['art'].show()
                self.shown_path = path
            else:
                self.failed_path = path
        except Exception:
            self.failed_path = path
