import requests

def get_live_rate(from_c: str, to_c: str):
    url = f"https://api.exchangerate.host/convert?from={from_c}&to={to_c}"
    
    try:
        res = requests.get(url, timeout=3).json()
        return res.get("result")
    except:
        return None