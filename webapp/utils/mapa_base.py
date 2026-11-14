"""Base dos mapas (Folium): camada de tiles do MapTiler Dataviz, com CARTO como reserva.

Usada pela página Mapa e pelos mapas das respostas do assistente.
"""
import folium

import config

RIO_CENTER = [-22.905, -43.33]


def tiles_layer(m: folium.Map) -> None:
    key = config._secret("MAPTILER_API_KEY")
    if key:
        folium.TileLayer(
            tiles=f"https://api.maptiler.com/maps/dataviz-light/256/{{z}}/{{x}}/{{y}}{{r}}.png?key={key}",
            attr='<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> '
                 '<a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap</a>',
            name="MapTiler Dataviz", max_zoom=19,
        ).add_to(m)
    else:
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name="CartoDB Positron", subdomains="abcd", max_zoom=19,
        ).add_to(m)
