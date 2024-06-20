import random
import string
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .models import URLMapping, URLMappingSchema
from django.db import transaction
from fastapi.responses import RedirectResponse
from django.core.cache import cache

app = FastAPI()


class Shortener:
    def __init__(self):
        self.real_base = "http://127.0.0.1:8000/api/"  # The actual URL prefix
        self.display_base = "http://eaziurl.fz/"  # The display URL prefix
        self.chars = string.ascii_letters + string.digits

    def _generate_short_key(self):
        # Generate a 6-character random short URL key
        return ''.join(random.choice(self.chars) for _ in range(6))

    def encode(self, longUrl: str, title: str = '') -> dict:

        with transaction.atomic():
            # 1️⃣ check if the long URL exists in cache
            cache_key = f"url:{longUrl}"
            cached_short_urls = cache.get(cache_key)
            if cached_short_urls:
                return cached_short_urls

            # 2️⃣Check if the long URL exists in the database
            mapping = URLMapping.objects.filter(long_url=longUrl).first()
            if mapping:
                short_urls = {
                    "real_url": self.real_base + mapping.short_url,
                    "display_url": self.display_base + mapping.short_url
                }
                # 3️⃣Cache the result
                cache.set(cache_key, short_urls)
                return short_urls

            #❗️️ Ensure the generated short key is unique
            while True:
                short_key = self._generate_short_key()
                if not URLMapping.objects.filter(short_url=short_key).exists():
                    break

            #♻️ Save the long URL and short URL to the database
            mapping = URLMapping(long_url=longUrl, short_url=short_key, title=title)
            mapping.save()

            short_urls = {
                "real_url": self.real_base + short_key,
                "display_url": self.display_base + short_key
            }
            #✅ Cache the result
            cache.set(cache_key, short_urls)
            return short_urls


shortener = Shortener()


class URLItem(BaseModel):
    url: str
    title: str = ''


@app.get("/test")
async def read_test():
    return {"message": "⭐️This is a test endpoint"}
# get all links
@app.get("/links", response_model=List[URLMappingSchema])
def get_all_links():
    links = URLMapping.objects.all()
    return [URLMappingSchema.from_orm(link) for link in links]

@app.post("/encode")
def encode_url(item: URLItem):
    short_urls = shortener.encode(item.url, item.title)
    return {
        "real_url": short_urls["real_url"],
        "display_url": short_urls["display_url"],
        "title": item.title
    }

@app.get("/{short_key}")
def redirect_url(short_key: str):
    cache_key = f"short:{short_key}"
    cached_long_url = cache.get(cache_key)
    if cached_long_url:
        return RedirectResponse(url=cached_long_url)

    mapping = URLMapping.objects.filter(short_url=short_key).first()
    if mapping:
        long_url = mapping.long_url
        cache.set(cache_key, long_url)
        return RedirectResponse(url=long_url)
    else:
        raise HTTPException(status_code=404, detail="URL not found")

