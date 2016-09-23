from subprocess import Popen
from xbmcswift2 import Plugin
import StringIO
import os
import re
import requests
import sys
import xbmc,xbmcaddon,xbmcvfs,xbmcgui,xbmcplugin
import zipfile
import operator
import HTMLParser
from sdAPI import SdAPI
import hashlib
import datetime,time
from utils import *
import sqlite3

plugin = Plugin()

def log(v):
    xbmc.log(repr(v))


def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

@plugin.route('/add_provider')
def add_provider():
    user = plugin.get_setting('sd.username')
    passw = plugin.get_setting('sd.password')
    passw = hashlib.sha1(passw.encode('utf-8')).hexdigest()
    sd = SdAPI(user=user, passw=passw)
    if not sd.logged_in:
        #TODO popup settings
        return
    #global sd
    status = 'You have %d / %d lineups' % (len(sd.lineups), sd.max_lineups)
    if sd.max_lineups - len(sd.lineups) < 1:
        xbmcgui.Dialog().ok(
            xbmcaddon.Addon().getAddonInfo('name'), status,
            'To add a new one you need to first remove one of your lineups')
        return

    country_list = sd.get_countries()
    countries = []
    for country in country_list:
        countries.append(country['fullName'])
    countries = sorted(countries, key=lambda s: s.lower())
    sel = xbmcgui.Dialog().select('Select country - %s' % status, list=countries)
    if sel >= 0:
        name = countries[sel]
        sel_country = [x for x in country_list if x["fullName"] == name]
        if len(sel_country) > 0:
            sel_country = sel_country[0]
            keyb = xbmc.Keyboard(sel_country['postalCodeExample'], 'Enter Post Code')
            keyb.doModal()
            if keyb.isConfirmed():
                lineup_list = sd.get_lineups(country=sel_country["shortName"], postcode=keyb.getText())
                lineups = []
                saved_lineups = sd.lineups
                for lineup in lineup_list:
                    if lineup['lineup'] not in saved_lineups:
                        lineups.append(lineup['name'])
                lineups = sorted(lineups, key=lambda s: s.lower())
                sel = xbmcgui.Dialog().select('Select lineup - not showing already selected...',
                                              list=lineups)
                if sel >= 0:
                    name = lineups[sel]
                    sel_lineup = [x for x in lineup_list if x["name"] == name]
                    if len(sel_lineup) > 0:
                        sel_lineup = sel_lineup[0]
                        xbmcgui.Dialog().notification(xbmcaddon.Addon().getAddonInfo('name'), 'Saving lineup...',
                                                      os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'icon.png'), 3000)
                        if sd.save_lineup(sel_lineup['lineup']):
                            xbmcgui.Dialog().notification(xbmcaddon.Addon().getAddonInfo('name'),
                                                          'Lineup "%s" saved' % name,
                                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'icon.png'), 5000)
                        else:
                            raise SourceException('Lineup could not be saved! '
                                                  'Check the log for details.')

@plugin.route('/remove_provider')
def remove_provider():
    user = plugin.get_setting('sd.username')
    passw = plugin.get_setting('sd.password')
    passw = hashlib.sha1(passw.encode('utf-8')).hexdigest()
    sd = SdAPI(user=user, passw=passw)
    #global sd, database
    lineup_list = sd.get_user_lineups()
    if len(lineup_list) == 0:
        return
    lineups = []
    for lineup in lineup_list:
        lineups.append(lineup['name'])
    lineups = sorted(lineups, key=lambda s: s.lower())
    sel = xbmcgui.Dialog().select('Current lineups - Click to delete...', list=lineups)
    if sel >= 0:
        name = lineups[sel]
        sel_lineup = [x for x in lineup_list if x["name"] == name]
        if len(sel_lineup) > 0:
            sel_lineup = sel_lineup[0]
            yes_no = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'),
                                            '[COLOR red]Deleting a lineup will also remove all '
                                            'channels associated with it![/COLOR]',
                                            'Do you want to continue?')
            if yes_no:
                xbmcgui.Dialog().notification(xbmcaddon.Addon().getAddonInfo('name'), 'Deleting lineup...',
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'icon.png'), 3000)
                if sd.delete_lineup(sel_lineup['lineup']):
                    #TODO
                    #database.deleteLineup(close, sel_lineup['lineup'])
                    xbmcgui.Dialog().notification(xbmcaddon.Addon().getAddonInfo('name'), 'Lineup "%s" deleted' % name,
                                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'icon.png'), 5000)

@plugin.route('/edit_channels')
def add_channels():
    user = plugin.get_setting('sd.username')
    passw = plugin.get_setting('sd.password')
    passw = hashlib.sha1(passw.encode('utf-8')).hexdigest()
    sd = SdAPI(user=user, passw=passw)
    #global sd
    lineup_list = sd.get_user_lineups()
    if len(lineup_list) == 0:
        return
    lineups = []
    for lineup in lineup_list:
        lineups.append(lineup['name'])
    lineups = sorted(lineups, key=lambda s: s.lower())
    sel = xbmcgui.Dialog().select('Select lineup', list=lineups)
    if sel < 0:
        return
    name = lineups[sel]
    sel_lineup = [x for x in lineup_list if x["name"] == name]
    if not len(sel_lineup):
        return        
    sel_lineup = sel_lineup[0]
    lineup = sel_lineup['lineup']
    station_list = sorted(sd.get_stations(lineup=lineup), key=lambda s: s.title.lower())
    xbmc.log(repr(station_list))
    if len(station_list) == 0:
        return
    stations = []
    for channel in station_list:
        xbmc.log(repr(channel))
        stations.append(channel.title)
    stations = sorted(stations, key=lambda s: s.lower())
    xbmc.log(repr(stations))
    sel = xbmcgui.Dialog().multiselect('Select lineup', stations)
    xbmc.log(repr(sel))
    if not sel:
        return
    
    path = xbmc.translatePath("special://profile/addon_data/script.schedules.direct/sd.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()    
    for s in sel:
        channel = station_list[s]
        c.execute("INSERT OR REPLACE INTO channels(lineup,id,title,logo) VALUES(?,?,?,?)",
                      [lineup,channel.id,channel.title,channel.logo])    
    conn.commit()                            
    c.close()
    #if sel < 0:
    #    return
    #name = lineups[sel]
    #sel_station = [x for x in station_list if x["name"] == name]
    #if not len(sel_station):
    #    return   
        
def to_local(time_str):
    # format: 2016-08-21T00:45:00Z
    try:
        utc = datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
    except TypeError:
        utc = datetime.datetime.fromtimestamp(
            time.mktime(time.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')))
    # get the local timezone offset in seconds
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = - (time.altzone if is_dst else time.timezone)
    td_local = datetime.timedelta(seconds=utc_offset)
    t_local = utc + td_local
    return t_local

@plugin.route('/export_xmltv')
def export_xmltv():
    progress_callback = None
    user = plugin.get_setting('sd.username')
    passw = plugin.get_setting('sd.password')
    passw = hashlib.sha1(passw.encode('utf-8')).hexdigest()
    sd = SdAPI(user=user, passw=passw)

    ch_list = []
    station_ids = []
    for ch in ch_list:
        station_ids.append(ch.id)
    station_ids = ["34135"]
    # make sure date is in UTC!
    date_local = datetime.datetime.now()
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = time.altzone if is_dst else time.timezone
    td_utc = datetime.timedelta(seconds=utc_offset)
    date = date_local + td_utc
    xbmc.log("[%s] Local date '%s' converted to UTC '%s'" %
             (xbmcaddon.Addon().getAddonInfo('id'), str(date_local), str(date)), xbmc.LOGDEBUG)

    # [{'station_id': station_id, 'p_id': p_id, 'start': start,
    #   'dur': dur, 'title': 'abc', 'desc': 'abc', 'logo': ''}, ... ]
    elements_parsed = 0
    schedules = sd.get_schedules(station_ids, date, progress_callback)
    for prg in schedules:
        start = to_local(prg['start'])
        end = start + datetime.timedelta(seconds=int(prg['dur']))
        result = Program(prg['station_id'], prg['title'], start, end, prg['desc'],
                         imageSmall=prg['logo'])
        xbmc.log(repr(result))
        elements_parsed += 1
        #if result:
        #    if progress_callback and elements_parsed % 100 == 0:
        #        if not progress_callback(100.0 / len(schedules) * elements_parsed):
        #            raise SourceUpdateCanceledException()
        #    yield result    


@plugin.route('/create_database')
def create_database():     
    path = xbmc.translatePath("special://profile/addon_data/script.schedules.direct/sd.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS channels(lineup TEXT, id TEXT, title TEXT, logo TEXT, stream_url TEXT, visible BOOLEAN, PRIMARY KEY (lineup,id))')
    c.execute('CREATE TABLE IF NOT EXISTS programs(station_id TEXT, p_id TEXT, title TEXT, logo TEXT, start TEXT, dur TEXT, desc TEXT, PRIMARY KEY (station_id,p_id))')
    c.close()
   
        
@plugin.route('/')
def index():
    items = []
    items.append(
    {
        'label': 'Create Database',
        'path': plugin.url_for('create_database'),
        'thumbnail':get_icon_path('settings'),
    })    
    items.append(
    {
        'label': 'Add TV Provider',
        'path': plugin.url_for('add_provider'),
        'thumbnail':get_icon_path('settings'),
    })
    items.append(
    {
        'label': 'Remove TV Provider',
        'path': plugin.url_for('remove_provider'),
        'thumbnail':get_icon_path('settings'),
    })
    items.append(
    {
        'label': 'Add Channels',
        'path': plugin.url_for('add_channels'),
        'thumbnail':get_icon_path('settings'),
    })
    items.append(
    {
        'label': 'Export xmltv',
        'path': plugin.url_for('export_xmltv'),
        'thumbnail':get_icon_path('settings'),
    })
    return items


if __name__ == '__main__':
    plugin.run()
