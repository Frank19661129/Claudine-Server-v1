"""
Widget Service - Handles external APIs for rich content widgets.
Part of Infrastructure layer.
"""
import os
import httpx
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import json


@dataclass
class WidgetIntent:
    """Detected widget intent from user message."""
    widget_type: Optional[str]  # 'map', 'weather', 'traffic', 'buienradar', 'image_search', None
    location: str  # For location-based widgets
    search_query: str  # For search-based widgets
    confidence: float


@dataclass
class WeatherData:
    """Weather information."""
    location: str
    temp: float
    feels_like: float
    humidity: int
    wind_speed: float
    description: str
    icon: str
    lat: float
    lng: float


@dataclass
class TrafficIncident:
    """Traffic incident information."""
    type: str  # 'file', 'ongeluk', 'werkzaamheden'
    description: str
    road: str
    location: str


@dataclass
class ImageSearchResult:
    """Image search result."""
    title: str
    thumbnail_url: str
    image_url: str
    source_url: str
    width: int
    height: int


class WidgetService:
    """
    Service for fetching data for rich content widgets.

    Integrates with:
    - Google Maps Geocoding API
    - OpenWeatherMap API
    - NDW Traffic API (Dutch road traffic)
    """

    def __init__(self):
        self.google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.openweather_key = os.getenv("OPENWEATHERMAP_API_KEY")
        self.google_search_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.google_search_cx = os.getenv("GOOGLE_SEARCH_CX")  # Custom Search Engine ID

    async def geocode_location(self, location: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Convert location name to latitude/longitude using Google Maps Geocoding API.

        Args:
            location: Location name (e.g., "Vianen", "Utrecht centrum")

        Returns:
            Tuple of (latitude, longitude) or (None, None) if not found
        """
        if not self.google_maps_key:
            return (None, None)

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{location}, Nederland",
            "key": self.google_maps_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("status") == "OK" and data.get("results"):
                    geo = data["results"][0]["geometry"]["location"]
                    return (geo["lat"], geo["lng"])

                return (None, None)
        except Exception as e:
            print(f"Geocoding error: {e}")
            return (None, None)

    async def get_weather_data(self, location: str) -> Optional[WeatherData]:
        """
        Fetch weather data from OpenWeatherMap API.

        Args:
            location: Location name

        Returns:
            WeatherData object or None if error
        """
        if not self.openweather_key:
            return None

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": f"{location},NL",
            "appid": self.openweather_key,
            "units": "metric",
            "lang": "nl",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("cod") == 200:
                    return WeatherData(
                        location=data["name"],
                        temp=data["main"]["temp"],
                        feels_like=data["main"]["feels_like"],
                        humidity=data["main"]["humidity"],
                        wind_speed=data["wind"]["speed"],
                        description=data["weather"][0]["description"],
                        icon=data["weather"][0]["icon"],
                        lat=data["coord"]["lat"],
                        lng=data["coord"]["lon"],
                    )

                return None
        except Exception as e:
            print(f"Weather API error: {e}")
            return None

    async def get_traffic_data(self, location: str) -> List[TrafficIncident]:
        """
        Fetch traffic information near a location.

        Note: This is a simplified implementation. For production, integrate with:
        - NDW (Nationaal Dataportaal Wegverkeer): https://www.ndw.nu/
        - ANWB Verkeersinformatie API

        Args:
            location: Location name

        Returns:
            List of TrafficIncident objects
        """
        # Get coordinates for location
        lat, lng = await self.geocode_location(location)

        if not lat or not lng:
            return []

        # TODO: Integrate with real traffic API
        # For now, return mock data as example
        # In production, call NDW API or ANWB API

        # Mock implementation - replace with real API
        mock_incidents = [
            TrafficIncident(
                type="file",
                description="5 minuten vertraging",
                road="A2",
                location=f"Richting Utrecht ter hoogte van {location}",
            ),
        ]

        # TODO: Real implementation:
        # try:
        #     async with httpx.AsyncClient() as client:
        #         # NDW Actuele Verkeersinformatie
        #         response = await client.get(
        #             "https://api.ndw.nu/api/v1/road-incidents",
        #             headers={"Accept": "application/json"}
        #         )
        #         data = response.json()
        #
        #         # Filter incidents near location (within ~20km radius)
        #         nearby_incidents = filter_by_distance(data, lat, lng, radius_km=20)
        #
        #         return [
        #             TrafficIncident(
        #                 type=classify_incident_type(incident),
        #                 description=incident["description"],
        #                 road=incident["road"],
        #                 location=incident["location"],
        #             )
        #             for incident in nearby_incidents
        #         ]
        # except Exception as e:
        #     print(f"Traffic API error: {e}")
        #     return []

        return mock_incidents

    async def get_image_search_results(self, query: str, num_results: int = 6) -> List[ImageSearchResult]:
        """
        Fetch image search results from Google Custom Search API.

        Args:
            query: Search query
            num_results: Number of results to return (max 10)

        Returns:
            List of ImageSearchResult objects
        """
        if not self.google_search_key or not self.google_search_cx:
            return []

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_search_key,
            "cx": self.google_search_cx,
            "q": query,
            "searchType": "image",
            "num": min(num_results, 10),  # Max 10 per request
            "safe": "active",  # Safe search
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("items"):
                    results = []
                    for item in data["items"]:
                        results.append(ImageSearchResult(
                            title=item.get("title", ""),
                            thumbnail_url=item.get("image", {}).get("thumbnailLink", ""),
                            image_url=item.get("link", ""),
                            source_url=item.get("image", {}).get("contextLink", ""),
                            width=item.get("image", {}).get("width", 0),
                            height=item.get("image", {}).get("height", 0),
                        ))
                    return results

                return []
        except Exception as e:
            print(f"Image search error: {e}")
            return []

    async def detect_widget_intent(
        self,
        user_message: str,
        anthropic_client=None,
    ) -> WidgetIntent:
        """
        Detect if user is asking for a widget using AI.

        Uses Claude API to understand user intent and extract location.

        Args:
            user_message: User's message
            anthropic_client: Anthropic client instance (optional)

        Returns:
            WidgetIntent with detected type and location
        """
        # Simple keyword-based detection as fallback
        # For production, use Claude API for better accuracy

        message_lower = user_message.lower()

        # Image search keywords
        image_search_keywords = [
            "laat me voorbeelden zien", "toon voorbeelden", "show me examples",
            "laat zien hoe", "hoe ziet", "foto's van", "fotos van", "afbeeldingen van",
            "pictures of", "images of", "voorbeelden van", "examples of",
            "inspiratie voor", "ideeën voor", "ideas for"
        ]

        # Visual/shopping related keywords (strong indicators for image search)
        visual_keywords = [
            "kapsels", "hairstyles", "kapsel", "haar",
            "kleding", "clothes", "outfit", "fashion", "mode",
            "trouwpak", "pak", "suit", "jurk", "dress",
            "schoenen", "shoes", "accessoires", "accessories",
            "interieur", "interior", "meubels", "furniture",
            "tattoo", "tattoos", "design", "art", "kunst"
        ]

        # Map keywords
        map_keywords = ["kaart", "map", "waar is", "locatie"]
        weather_keywords = ["weer", "weerbericht", "temperatuur", "graden", "zon", "regen", "bewolkt"]
        traffic_keywords = ["verkeer", "file", "drukte", "a2", "a1", "snelweg", "weg"]
        buienradar_keywords = ["buienradar", "radar", "neerslag", "wanneer gaat het regenen"]

        widget_type = None
        confidence = 0.0
        location = ""
        search_query = ""

        # Check for image search (highest priority for visual queries)
        has_image_keyword = any(keyword in message_lower for keyword in image_search_keywords)
        has_visual_keyword = any(keyword in message_lower for keyword in visual_keywords)

        if has_image_keyword or has_visual_keyword:
            widget_type = "image_search"
            confidence = 0.95 if has_image_keyword else 0.85
            # Extract the search query (remove trigger words)
            search_query = user_message
            for keyword in ["laat me voorbeelden zien van", "toon voorbeelden van",
                          "laat zien", "foto's van", "afbeeldingen van", "voorbeelden van"]:
                search_query = search_query.lower().replace(keyword, "").strip()

        # Check for buienradar (most specific location widget)
        elif any(keyword in message_lower for keyword in buienradar_keywords):
            widget_type = "buienradar"
            confidence = 0.9
            location = self._extract_location_simple(user_message)

        # Check for traffic
        elif any(keyword in message_lower for keyword in traffic_keywords):
            widget_type = "traffic"
            confidence = 0.85
            location = self._extract_location_simple(user_message)

        # Check for weather
        elif any(keyword in message_lower for keyword in weather_keywords):
            widget_type = "weather"
            confidence = 0.9
            location = self._extract_location_simple(user_message)

        # Check for map
        elif any(keyword in message_lower for keyword in map_keywords):
            widget_type = "map"
            confidence = 0.8
            location = self._extract_location_simple(user_message)

        # TODO: Use Claude API for better detection
        # if anthropic_client:
        #     try:
        #         system_prompt = """
        #         Detecteer of de gebruiker om een van de volgende widgets vraagt:
        #         - MAP: kaart, locatie tonen, waar is X
        #         - WEATHER: weer, temperatuur, zon, regen
        #         - TRAFFIC: verkeer, file, drukte op de weg
        #         - BUIENRADAR: buienradar, radar, neerslag
        #
        #         Output ALLEEN JSON (geen andere tekst):
        #         {
        #           "widget_type": "map|weather|traffic|buienradar|none",
        #           "location": "extracted location",
        #           "confidence": 0.0-1.0
        #         }
        #         """
        #
        #         response = await anthropic_client.messages.create(
        #             model="claude-3-haiku-20240307",
        #             max_tokens=256,
        #             system=system_prompt,
        #             messages=[{"role": "user", "content": user_message}]
        #         )
        #
        #         # Parse JSON response
        #         result = json.loads(response.content[0].text)
        #
        #         return WidgetIntent(
        #             widget_type=result.get("widget_type") if result.get("widget_type") != "none" else None,
        #             location=result.get("location", ""),
        #             confidence=result.get("confidence", 0.0),
        #         )
        #     except Exception as e:
        #         print(f"AI intent detection error: {e}")
        #         # Fall through to keyword-based detection

        return WidgetIntent(
            widget_type=widget_type,
            location=location,
            search_query=search_query if search_query else user_message,
            confidence=confidence,
        )

    def _extract_location_simple(self, message: str) -> str:
        """
        Simple location extraction from message.
        Looks for common Dutch location patterns.

        Examples:
        - "bij Vianen" -> "Vianen"
        - "in Utrecht" -> "Utrecht"
        - "van Amsterdam" -> "Amsterdam"
        """
        # Common prepositions before location
        prepositions = ["bij", "in", "te", "van", "naar", "rond", "rondom", "nabij"]

        words = message.split()

        for i, word in enumerate(words):
            word_lower = word.lower().strip("?.,!")

            if word_lower in prepositions and i + 1 < len(words):
                # Next word is likely the location
                location = words[i + 1].strip("?.,!")
                # Capitalize first letter
                return location.capitalize()

        # No preposition found, try to find capitalized word (place name)
        for word in words:
            cleaned = word.strip("?.,!")
            if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
                return cleaned

        return ""

    async def create_map_widget_data(self, location: str) -> Dict[str, Any]:
        """Create widget data for map."""
        lat, lng = await self.geocode_location(location)

        return {
            "type": "map",
            "data": {
                "location": location,
                "lat": lat,
                "lng": lng,
                "zoom": 12,
                "map_type": "roadmap",
            }
        }

    async def create_weather_widget_data(self, location: str) -> Dict[str, Any]:
        """Create widget data for weather."""
        weather = await self.get_weather_data(location)

        if not weather:
            return {
                "type": "weather",
                "data": {
                    "location": location,
                    "error": "Kon weergegevens niet ophalen",
                }
            }

        return {
            "type": "weather",
            "data": {
                "location": weather.location,
                "lat": weather.lat,
                "lng": weather.lng,
                "current": {
                    "temp": weather.temp,
                    "feels_like": weather.feels_like,
                    "humidity": weather.humidity,
                    "wind_speed": weather.wind_speed,
                    "description": weather.description,
                    "icon": weather.icon,
                }
            }
        }

    async def create_traffic_widget_data(self, location: str) -> Dict[str, Any]:
        """Create widget data for traffic."""
        incidents = await self.get_traffic_data(location)
        lat, lng = await self.geocode_location(location)

        return {
            "type": "traffic",
            "data": {
                "location": location,
                "lat": lat,
                "lng": lng,
                "incidents": [
                    {
                        "type": inc.type,
                        "description": inc.description,
                        "road": inc.road,
                        "location": inc.location,
                    }
                    for inc in incidents
                ]
            }
        }

    async def create_buienradar_widget_data(self, location: str) -> Dict[str, Any]:
        """Create widget data for buienradar."""
        lat, lng = await self.geocode_location(location)

        if not lat or not lng:
            # Default to center of Netherlands
            lat, lng = 52.1326, 5.2913

        return {
            "type": "buienradar",
            "data": {
                "location": location,
                "lat": lat,
                "lng": lng,
            }
        }

    async def create_image_search_widget_data(self, query: str) -> Dict[str, Any]:
        """Create widget data for image search."""
        results = await self.get_image_search_results(query)

        # Generate Pinterest and Google search URLs
        pinterest_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
        google_images_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"

        return {
            "type": "image_search",
            "data": {
                "query": query,
                "results": [
                    {
                        "title": result.title,
                        "thumbnail_url": result.thumbnail_url,
                        "image_url": result.image_url,
                        "source_url": result.source_url,
                        "width": result.width,
                        "height": result.height,
                    }
                    for result in results
                ],
                "pinterest_url": pinterest_url,
                "google_url": google_images_url,
            }
        }

    async def create_widget_for_intent(self, intent: WidgetIntent) -> Optional[Dict[str, Any]]:
        """
        Create widget data based on detected intent.

        Args:
            intent: Detected widget intent

        Returns:
            Widget data dict or None if no widget needed
        """
        if not intent.widget_type:
            return None

        if intent.widget_type == "image_search":
            return await self.create_image_search_widget_data(intent.search_query)
        elif intent.widget_type == "map":
            if not intent.location:
                return None
            return await self.create_map_widget_data(intent.location)
        elif intent.widget_type == "weather":
            if not intent.location:
                return None
            return await self.create_weather_widget_data(intent.location)
        elif intent.widget_type == "traffic":
            if not intent.location:
                return None
            return await self.create_traffic_widget_data(intent.location)
        elif intent.widget_type == "buienradar":
            if not intent.location:
                return None
            return await self.create_buienradar_widget_data(intent.location)

        return None
