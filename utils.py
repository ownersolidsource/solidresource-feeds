# utils.py
import re, datetime as dt
from email.utils import format_datetime
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def parse_money_like(s):
    if not s: return None
    x = s.strip().replace(',', '').upper()
    m = re.match(r'^([0-9]*\.?[0-9]+)\s*([KMB])?$', x)
    if m:
        val = float(m.group(1)); suf = m.group(2)
        if suf == 'K': val *= 1_000
        elif suf == 'M': val *= 1_000_000
        elif suf == 'B': val *= 1_000_000_000
        return val
    try:
        return float(x)
    except:
        return None

def parse_percent(s):
    if not s: return None
    x = s.strip().replace('%', '')
    try: return float(x)
    except: return None

def clean_text(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()

def now_rfc2822():
    return format_datetime(dt.datetime.utcnow())

def _session(ua):
    s = requests.Session()
    # Do NOT inherit system proxies (can cause hangs on some Windows setups)
    s.trust_env = False
    retries = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": ua, "Connection": "close"})
    return s

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def fetch(url, ua, timeout=20):
    """
    timeout can be an int or tuple: (connect_timeout, read_timeout)
    We use a short connect and modest read so slow sites can't freeze the run.
    """
    if isinstance(timeout, (int, float)):
        timeout = (5, timeout)        # 5s connect, <timeout>s read
    sess = _session(ua)
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text
