from flask import Flask, render_template, jsonify, request, redirect, session
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import base64
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)



sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=SCOPE,
    cache_path='.spotipyoauthcache',
    show_dialog=True
)

def milliseconds_to_time(ms):
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

def get_spotify_client():
    token_info = sp_oauth.get_cached_token()
    if token_info:
        return spotipy.Spotify(auth=token_info['access_token'])
    return None

@app.route('/auth-status')
def auth_status():
    try:
        token_info = sp_oauth.get_cached_token()
        status = {
            'is_authenticated': bool(token_info),
            'token_expiry': token_info.get('expires_at') if token_info else None
        }
        return jsonify({"status": "success", "data": status})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/logout')
def logout():
    try:
        if os.path.exists('.spotipyoauthcache'):
            os.remove('.spotipyoauthcache')
        return jsonify({"status": "success", "message": "Successfully logged out"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/spotify-login')
def spotify_login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/')

@app.route('/now-playing')
def now_playing():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"status": "not_authenticated"})
    
    try:
        current_track = sp.current_user_playing_track()
        if current_track is None:
            return jsonify({"status": "not_playing"})
        
        user_info = sp.current_user()
        return jsonify({
            "status": "playing",
            "track_name": current_track['item']['name'],
            "artist": current_track['item']['artists'][0]['name'],
            "album_art": current_track['item']['album']['images'][0]['url'],
            "spotify_link": current_track['item']['external_urls']['spotify'],
            "display_name": user_info['display_name']
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/recently-played')
def recently_played():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"status": "not_authenticated"})
    
    try:
        results = sp.current_user_recently_played(limit=50)
        items = [{
            'name': track['track']['name'],
            'artist': track['track']['artists'][0]['name'],
            'album_art': track['track']['album']['images'][0]['url'],
            'duration': milliseconds_to_time(track['track']['duration_ms']),
            'spotify_url': track['track']['external_urls']['spotify']
        } for track in results['items']]
        
        return jsonify({"status": "success", "items": items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/playlists')
def playlists():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"status": "not_authenticated"})
    
    try:
        results = sp.current_user_playlists()
        items = [{
            'name': playlist['name'],
            'image': playlist['images'][0]['url'] if playlist['images'] else '',
            'tracks': playlist['tracks']['total'],
            'spotify_url': playlist['external_urls']['spotify']
        } for playlist in results['items']]
        
        return jsonify({"status": "success", "items": items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/top-tracks')
def top_tracks():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"status": "not_authenticated"})
    
    try:
        results = sp.current_user_top_tracks(limit=50, time_range='medium_term')
        items = [{
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'album_art': track['album']['images'][0]['url'],
            'duration': milliseconds_to_time(track['duration_ms']),
            'spotify_url': track['external_urls']['spotify']
        } for track in results['items']]
        
        return jsonify({"status": "success", "items": items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/weather/current/<location>")
def get_current_weather(location):
    try:
        response = requests.get(f"https://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={location}")
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/weather/forecast/<location>")
def get_weather_forecast(location):
    try:
        response = requests.get(f"https://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={location}&days=3")
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return 'No URL provided', 400
    
    js_whitelist = json.load(open("static/js_whitelist.json", "r"))

    if not urlparse(url).scheme:
        url = 'http://' + url
    
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    js_enabled = domain in js_whitelist
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        content_type = response.headers.get('content-type', '')
        
        if 'text/html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            if not js_enabled:
                for script in soup(["script"]):
                    script.decompose()
            
            for iframe in soup(["iframe"]):
                iframe.decompose()
            
            base_tag = soup.new_tag('base', href=url)
            if soup.head:
                soup.head.insert(0, base_tag)
            else:
                head = soup.new_tag('head')
                head.append(base_tag)
                soup.html.insert(0, head)
            
            csp_value = "default-src 'self' 'unsafe-inline' data: *;"
            if js_enabled:
                csp_value = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: *;"
            
            meta_csp = soup.new_tag('meta', attrs={
                'http-equiv': 'Content-Security-Policy',
                'content': csp_value
            })
            soup.head.append(meta_csp)
            
            status_div = soup.new_tag('div', attrs={
                'style': '''
                    position: fixed;
                    top: 0;
                    right: 0;
                    padding: 5px 10px;
                    background: rgba(0,0,0,0.7);
                    color: white;
                    font-size: 12px;
                    z-index: 9999;
                '''
            })
            status_div.string = 'JavaScript Enabled' if js_enabled else 'JavaScript Disabled'
            soup.body.append(status_div)
            
            return str(soup)
        else:
            return response.content, 200, {'Content-Type': content_type}
            
    except Exception as e:
        return str(e), 500

@app.route('/suggestions/send', methods=['POST'])
def send_suggestion():
    suggestion = request.json.get('suggestion')
    if suggestion:
        url = 'https://discord.com/api/webhooks/1312186950907858964/f_HI6-JsgdAgiyS0rFooDGZFV6cQFxaxzTNHL0k1kYh2CXAamERRtpm892Jci2kV7OqG'
        data = {'content': "**NEW SUGGESTION: **\n" + suggestion}
        response = requests.post(url, data=data)
        if response.status_code == 204:
            return jsonify({'success': True})
    return jsonify({'error': 'Failed to send suggestion'}), 400

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(port=5500, debug=True)