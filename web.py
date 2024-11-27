from flask import Flask, render_template, jsonify, request, redirect, session
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = os.urandom(24)


SCOPE = "user-modify-playback-state user-read-playback-state user-read-private streaming"

sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=SCOPE,
    cache_path='.spotipyoauthcache',
    show_dialog=True
)

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

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return 'No URL provided', 400
    
    # Whitelist of domains where JavaScript is allowed
    js_whitelist = {
    # Your domains
    'f1shy312.com',
    'ubuntu.f1shy312.com',
    'termfolio.f1shy312.com',
    'www.trynocs.com',
    'www.trynocs.de',
    'www.galitube.xyz',
    'galitube.xyz',
    
    # Major tech companies and their services
    'github.com', 'www.github.com', 'raw.githubusercontent.com', 'gist.github.com',
    'gitlab.com', 'www.gitlab.com',
    'google.com', 'www.google.com', 'accounts.google.com', 'docs.google.com', 'drive.google.com', 'mail.google.com', 'calendar.google.com',
    'microsoft.com', 'www.microsoft.com', 'outlook.com', 'office.com', 'live.com', 'azure.com', 
    'apple.com', 'www.apple.com', 'icloud.com',
    'amazon.com', 'www.amazon.com', 'aws.amazon.com', 'cloudfront.net',
    
    # Social media
    'facebook.com', 'www.facebook.com', 'fb.com', 'm.facebook.com',
    'twitter.com', 'www.twitter.com', 'x.com',
    'instagram.com', 'www.instagram.com',
    'linkedin.com', 'www.linkedin.com',
    'reddit.com', 'www.reddit.com', 'old.reddit.com', 'np.reddit.com',
    'pinterest.com', 'www.pinterest.com',
    'tumblr.com', 'www.tumblr.com',
    
    # Developer resources
    'stackoverflow.com', 'www.stackoverflow.com', 'stackexchange.com',
    'npmjs.com', 'www.npmjs.com',
    'pypi.org', 'www.pypi.org',
    'python.org', 'www.python.org', 'docs.python.org',
    'mozilla.org', 'www.mozilla.org', 'developer.mozilla.org',
    'w3schools.com', 'www.w3schools.com',
    'jsdelivr.com', 'www.jsdelivr.com',
    'cloudflare.com', 'www.cloudflare.com',
    
    # Education
    'coursera.org', 'www.coursera.org',
    'udemy.com', 'www.udemy.com',
    'edx.org', 'www.edx.org',
    'khanacademy.org', 'www.khanacademy.org',
    'mit.edu', 'www.mit.edu',
    'stanford.edu', 'www.stanford.edu',
    
    # Entertainment
    'youtube.com', 'www.youtube.com', 'youtu.be',
    'netflix.com', 'www.netflix.com',
    'spotify.com', 'www.spotify.com', 'open.spotify.com',
    'twitch.tv', 'www.twitch.tv',
    'discord.com', 'www.discord.com',
    'steamcommunity.com', 'www.steamcommunity.com',
    'steampowered.com', 'store.steampowered.com',
    
    # News and information
    'medium.com', 'www.medium.com',
    'wikipedia.org', 'www.wikipedia.org',
    'nytimes.com', 'www.nytimes.com',
    'bbc.com', 'www.bbc.com', 'bbc.co.uk',
    'cnn.com', 'www.cnn.com',
    'reuters.com', 'www.reuters.com',
    
    # Productivity
    'notion.so', 'www.notion.so',
    'trello.com', 'www.trello.com',
    'asana.com', 'www.asana.com',
    'slack.com', 'www.slack.com',
    'zoom.us', 'www.zoom.us',
    
    # Cloud services
    'dropbox.com', 'www.dropbox.com',
    'box.com', 'www.box.com',
    'digitalocean.com', 'www.digitalocean.com',
    'heroku.com', 'www.heroku.com',
    'netlify.com', 'www.netlify.com',
    'vercel.com', 'www.vercel.com',
    
    # Payment services
    'paypal.com', 'www.paypal.com',
    'stripe.com', 'www.stripe.com',
    
    # Search engines
    'bing.com', 'www.bing.com',
    'duckduckgo.com', 'www.duckduckgo.com',
    'yahoo.com', 'www.yahoo.com',
    
    # Tech news
    'techcrunch.com', 'www.techcrunch.com',
    'theverge.com', 'www.theverge.com',
    'wired.com', 'www.wired.com',
    'engadget.com', 'www.engadget.com',
    
    # Web tools
    'codepen.io', 'www.codepen.io',
    'jsfiddle.net', 'www.jsfiddle.net',
    'replit.com', 'www.replit.com',
    'codesandbox.io', 'www.codesandbox.io',
    
    # Documentation
    'readthedocs.org', 'www.readthedocs.org',
    'docs.rs', 'www.docs.rs',
    'jquery.com', 'www.jquery.com',
    'reactjs.org', 'www.reactjs.org',
    'vuejs.org', 'www.vuejs.org',
    'angular.io', 'www.angular.io',

}

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
            
            # Handle scripts based on whitelist
            if not js_enabled:
                for script in soup(["script"]):
                    script.decompose()
            
            # Remove iframes regardless of whitelist status
            for iframe in soup(["iframe"]):
                iframe.decompose()
            
            # Add base tag for relative URLs
            base_tag = soup.new_tag('base', href=url)
            if soup.head:
                soup.head.insert(0, base_tag)
            else:
                head = soup.new_tag('head')
                head.append(base_tag)
                soup.html.insert(0, head)
            
            # Add CSP meta tag with appropriate settings
            csp_value = "default-src 'self' 'unsafe-inline' data: *;"
            if js_enabled:
                csp_value = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: *;"
            
            meta_csp = soup.new_tag('meta', attrs={
                'http-equiv': 'Content-Security-Policy',
                'content': csp_value
            })
            soup.head.append(meta_csp)
            
            # Add visual indicator for JavaScript status
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

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(port=5500, debug=True)