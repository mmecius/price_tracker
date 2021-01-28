import requests
from bs4 import BeautifulSoup

response = requests.get("https://pigu.lt/lt/foto-gsm-mp3/mobilieji-telefonai/telefonas-xiaomi-redmi-note-9-pro-64-gb?id=31284326&feat=search&keyword=xiaomi+redmi+note+9+pro")
soup = BeautifulSoup(response.text, "html.parser")

product_name = soup.find(name="h1")
print(product_name.getText())
product_price = soup.find(name="div", class_="product-price fl")
print(product_price.getText()[::2])