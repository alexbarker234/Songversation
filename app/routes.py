from flask import render_template, request, url_for, session, redirect, jsonify
import time

from app import app, db
from app.models import Track, TrackLyrics, Lyric

from datetime import datetime

import requests, asyncio, aiohttp

from config import Config

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SECONDS_IN_HOUR = 3600
SECONDS_IN_DAY = SECONDS_IN_HOUR * 24

'''
TODO:
- caching
 - button for user to delete their cache? 
 -
'''
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home', userdata=UserData())

@app.route('/lyricgame')
def lyricGame():
    return render_template('lyricgame.html', title='Home', userdata=UserData())


@app.route('/login')
def login():    
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/logout')
def logout():    
    for key in list(session.keys()):
        session.pop(key)
    return redirect('/')

@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect("/index")

#TODO: redo this to use code like below
@app.route('/topartists', methods=['GET'])
def topArtists():
    session['token_info'], authorized = get_token()
    session.modified = True
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    results = []
    iter = 0

    limit = 20

    while True:
        offset = iter * limit
        iter += 1
        curGroup = sp.current_user_top_artists(limit=limit, offset=offset, time_range='short_term')['items']
        for idx, item in enumerate(curGroup):
            results += [Artist(item)]
        if (len(curGroup) < limit):
            break
    
    return jsonify([ob.__dict__ for ob in results])

@app.route('/getplaylists')
def get_playlists():
    session['token_info'], authorized = get_token()
    session.modified = True
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    
    results = []

    playlists = sp.current_user_playlists(limit=50,offset=0)
    while playlists:
        for i, playlist in enumerate(playlists['items']):
            platlistObj = Playlist(playlist)
            if platlistObj.trackCount > 0:
                results.append(platlistObj)
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None
    return jsonify([ob.__dict__ for ob in results])

@app.route('/getplaylisttracks/<playlist_id>')
def get_playlist_tracks(playlist_id):
    session['token_info'], authorized = get_token()
    session.modified = True
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    
    results = []

    print('Fetching Tracks for playlist id: ' + playlist_id)

    tracks = sp.playlist_tracks(playlist_id = playlist_id, limit = 50,offset = 0)
    while tracks:
        for i, playlistTrack in enumerate(tracks['items']):
            # dont add local files 
            if playlistTrack['track']['is_local'] or playlistTrack['track']['id'] != None:
                results.append(Track(playlistTrack['track']))
        if tracks['next']:
            tracks = sp.next(tracks)
        else:
            tracks = None

    return jsonify([ob.__dict__ for ob in results])

@app.route('/testing/<param>')
def testing(param):
    # no lyrics: 6k35OOYim5XTSwb1rYW9lT
    # lyrics : 6tnedmxMVEHzPJfWucWzHo
    return get_track_lyrics(param)

@app.route('/gettracklyrics', methods=['GET'])
async def get_track_lyrics():
    return_data = {
        'error': False,
        'track_lyrics': {}
    }

    track_ids = request.args.get('track_ids').split(',')
    if len(track_ids) == 0:
        return_data['error'] = True
        return_data['error_message'] = "No track ids entered"

    # init
    for track_id in track_ids:
        return_data['track_lyrics'][track_id] = []

    # check cache
    uncached_track_ids = []
    for track_id in track_ids:
        lyric_cache = TrackLyrics.query.filter_by(track_id = track_id).first()
        if lyric_cache:
            lyric_lines_cache = Lyric.query.filter_by(track_lyric_id = lyric_cache.id).order_by(Lyric.order.asc()).all()

            # check if cache is old
            needs_refresh = False
            if (datetime.utcnow() - lyric_cache.last_cache_date).total_seconds() > SECONDS_IN_DAY:
                print(f"Cache expired for track_id: {track_id}")
                needs_refresh = True
            elif lyric_cache.lyric_count != len(lyric_lines_cache):
                print(f"Mismatch between lyric count and lines recieved: count: {lyric_cache.lyric_count}, lines: {len(lyric_lines_cache)}")
                needs_refresh = True

            if len(lyric_lines_cache) > 0:      
                for lyric in lyric_lines_cache:
                    # delete all lyric caches if they are old
                    if needs_refresh:
                        db.session.delete(lyric)
                    # add the lyrics to the list
                    else:
                        return_data['track_lyrics'][track_id].append(lyric.lyric)
        if not lyric_cache or needs_refresh:
            uncached_track_ids.append(track_id)

    if len(uncached_track_ids) > 0: 
        # asynchrnously get all uncached lyrics
        async with aiohttp.ClientSession() as session:
            tasks = []
            for track_id in uncached_track_ids:
                    tasks.append(
                        fetch(session, "https://spotify-lyric-api.herokuapp.com/?trackid=" + track_id, track_id)
                    )
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # process responses
            for response in responses:
                track_id = response['data']

                lyric_cache = TrackLyrics.query.filter_by(track_id = track_id).first()

                # initialise cache 
                if not lyric_cache:
                    lyric_cache = TrackLyrics(track_id = track_id)
                    db.session.add(lyric_cache)
                    # required in order to use lyric_cache.id
                    db.session.flush()
                    db.session.refresh(lyric_cache)
                
                lyricCount = 0

                # No lyrics returns 404
                if not response['json']['error']:
                    # turn response into list of each lyric
                    for line in response['json']['lines']:
                        if not line or not line['words']  or line['words'] == '♪': 
                            continue
                        return_data['track_lyrics'][track_id].append(line['words'])
                        lyric_line = Lyric(lyric = line['words'], order = lyricCount, track_lyric_id = lyric_cache.id)
                        db.session.add(lyric_line)
                        lyricCount += 1

                # update cache
                lyric_cache.lyric_count = lyricCount
                lyric_cache.last_cache_date = datetime.utcnow()

                print("Caching lyrics for track_id:" + track_id )

    db.session.commit()
    return jsonify(return_data)

# Checks to see if token is valid and gets a new token if not
def get_token():
    token_valid = False
    token_info = session.get("token_info", {})

    # Checking if the session already has a token stored
    if not (session.get('token_info', False)):
        token_valid = False
        return token_info, token_valid

    # Checking if token has expired
    now = int(time.time())
    is_token_expired = session.get('token_info').get('expires_at') - now < 60

    # Refreshing token if it has expired
    if (is_token_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(session.get('token_info').get('refresh_token'))

    token_valid = True
    return token_info, token_valid

def create_spotify_oauth():
    return SpotifyOAuth(
            client_id = Config.SPOTIPY_CLIENT_ID,
            client_secret = Config.SPOTIPY_CLIENT_SECRET,
            redirect_uri = url_for('authorize', _external=True),
            scope = "user-library-read user-top-read playlist-read-private")

# expanded upon https://dev.to/matteo/async-request-with-python-1hpo
async def fetch(session, url, data):
    """Execute an http call async
    Args:
        session: context for making the http call
        url: URL to call
        data: optional, additional data attached to the call
    Return:
        A dictionary containing 'url', 'json' dictionary of response & additional data attached to the call
    """ 
    async with session.get(url) as response:
            resp = await response.json()
            return { 'url': url, 'json': resp, 'data': data }
    
class UserData:
    def __init__(self):
        session['token_info'], self.authorized = get_token()
        session.modified = True
        if self.authorized:
            sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
            payload = sp.me()
            self.username = payload['display_name']     
            self.image_url = payload['images'][0]['url'] if len(payload['images']) > 0 else None
            self.id = payload['id']

class Artist:
    def __init__(self, payload):
        self.name = payload['name']
        self.image = payload['images'][0]['url'] if len(payload['images']) > 0 else None

class Playlist:
    def __init__(self, payload):
        self.name = payload['name']
        self.id = payload['id']
        self.ownerID = payload['owner']['id']
        self.trackCount = payload['tracks']['total']
        if len(payload['images']) > 0:
            self.image = payload['images'][0]['url']
        # default icon
        else:
            self.image = url_for('static', filename='defaultCover.png')

class Track:
    def __init__(self, payload):
        self.name = payload['name']
        self.id = payload['id']
        self.artists = []
        for artist in payload['artists']:
            self.artists.append(artist['name'])
        # PREVIEW CAN BE NULL
        self.preview_url = payload['preview_url']

