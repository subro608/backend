import requests

url = "https://online.goinglobal.com/h1b-opt/opt-listing?page=0"

payload = {}
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,/;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "cookie": "_gid=GA1.2.861861737.1732735303; _ga_ENZPEE7X1Z=GS1.1.1732735302.1.1.1732735322.0.0.0; SSESSb78c3ea8d560fb4f53b08dbf7ce3a0a5=P0nEPplvxU5JlUo26X44oPNLDO33g2c1lpYpgKuzN1A; ggcii=17824; _gat=1; _ga=GA1.1.854032289.1732735303; _ga_VX07G3NFLC=GS1.1.1732735393.1.1.1732735673.60.0.0; SSESSb78c3ea8d560fb4f53b08dbf7ce3a0a5=CrVaiEUL6vWcBoTTk_TLUuhPYw-gr8KctbSSC1Do6EY",
    "priority": "u=0, i",
    "referer": "https://online.goinglobal.com/h1b-opt/opt-listing?page=6",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)
