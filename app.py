import streamlit as st
import requests
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import math

st.set_page_config(page_title="Florida SCIP Map Beast", layout="wide")
st.title("🗺️ Florida SCIP Map Beast 🌴🔥")
st.sidebar.header("Inputs")

geolocator = Nominatim(user_agent="scip_map_app")

opencellid_token = st.sidebar.text_input("OpenCellID Token", value="pk.6d4e560229de9121955a48aa246647b2", type="password")

location_input = st.sidebar.text_input("Location (address or lat,lon)", "Miami, FL")
radius_mi = st.sidebar.selectbox("Radius (miles)", [0.25, 0.50, 1.0], index=1)
radius_m = radius_mi * 1609.344

if st.sidebar.button("Generate Map 🚀"):
    with st.spinner("Building your SCIP beast..."):
        # Improved Geocode
        if "," in location_input.strip():
            try:
                parts = [p.strip() for p in location_input.split(",")]
                lat, lon = float(parts[0]), float(parts[1])
            except:
                st.error("Invalid lat,lon format 🤷 Try '25.7617, -80.1918'")
                st.stop()
        else:
            query = location_input.strip()
            if not query.lower().endswith(("florida", "fl")):
                query += ", Florida"
            loc = geolocator.geocode(query)
            if not loc:
                st.error("Address not found 🤷 Try more details or lat,lon")
                st.stop()
            lat, lon = loc.latitude, loc.longitude
        
        # Airports
        airports_url = "https://ourairports.com/data/airports.csv"
        df_airports = pd.read_csv(airports_url)
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        df_airports["dist"] = df_airports.apply(lambda row: haversine(lat, lon, row.latitude_deg, row.longitude_deg) if pd.notna(row.latitude_deg) else np.inf, axis=1)
        closest_airport = df_airports.loc[df_airports["dist"].idxmin()]
        
        airports_js = f'L.marker([{closest_airport.latitude_deg}, {closest_airport.longitude_deg}]).bindTooltip("{closest_airport.name} ({closest_airport.iata_code or "N/A"})", {{permanent: true}}).bindPopup("<b>Closest Airport</b><br>{closest_airport.name}<br>Dist: {closest_airport.dist/1000:.1f} km").addTo(airportsLayer);\n'
        
        # Cell towers - improved handling
        cells_js = ""
        try:
            bbox_pad = radius_m * 1.5 / 111000
            min_lat = lat - bbox_pad
            max_lat = lat + bbox_pad
            min_lon = lon - (bbox_pad / math.cos(math.radians(lat)))
            max_lon = lon + (bbox_pad / math.cos(math.radians(lat)))
            url = "https://opencellid.org/ocid-api/cells/getInArea"
            params = {"token": opencellid_token, "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}", "limit": 200, "format": "json"}
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            cells = data.get("cells", [])
            if cells:
                df_cells = pd.DataFrame(cells)
                df_cells = df_cells.dropna(subset=["lat", "lon"])
                df_cells["dist"] = df_cells.apply(lambda row: haversine(lat, lon, row.lat, row.lon), axis=1)
                closest_idx = df_cells["dist"].idxmin()
                for idx, row in df_cells.iterrows():
                    tech = row.get("radio", "Unknown")
                    color = {"GSM": "#00ff00", "UMTS": "#0000ff", "LTE": "#ff0000", "NR": "#ff00ff", "CDMA": "#ffff00"}.get(tech, "#888888")
                    tooltip = f"{tech} {row.get('mcc', '?')}-{row.get('net', '?')}"
                    popup = f"<b>Cell Tower</b><br>Radio: {tech}<br>MCC-MNC: {row.get('mcc')}-{row.get('net')}<br>Cell ID: {row.get('cell')}<br>Range: {row.get('range', 'N/A')}m"
                    style = f"radius: 6, fillColor: '{color}', weight: 1, opacity: 0.8, fillOpacity: 0.8"
                    if idx == closest_idx:
                        style = "radius: 12, fillColor: 'yellow', color: 'red', weight: 4, fillOpacity: 1"
                        tooltip += " ← CLOSEST"
                    cells_js += f'L.circleMarker([{row.lat}, {row.lon}], {{{style}}}).bindTooltip("{tooltip}").bindPopup("{popup}").addTo(cellsLayer);\n'
        except Exception as e:
            st.warning(f"Cell towers skipped (API hiccup: {str(e)}) — common with free limits, still badass map! 📡")
        
        # Full HTML
        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SCIP Map - {location_input}</title>
            <meta charset="utf-8"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css"/>
            <style>#map {{height: 100vh;}}</style>
        </head>
        <body>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="https://unpkg.com/esri-leaflet@3.0.8/dist/esri-leaflet.js"></script>
            <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
            <script>
                var map = L.map('map').setView([{lat}, {lon}], 15);
                
                var satellite = L.esri.basemapLayer('Imagery');
                var topo = L.esri.basemapLayer('Topographic');
                var streets = L.esri.basemapLayer('Streets');
                var usgsTopo = L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{{z}}/{{y}}/{{x}}', {{attribution: 'USGS'}});
                
                var baseLayers = {{"Satellite": satellite, "Topographic": topo, "Streets": streets, "USGS Topo": usgsTopo}};
                
                var overlays = {{}};
                var shading = L.esri.basemapLayer('ShadedRelief');
                overlays['Hillshading'] = shading;
                var transport = L.esri.basemapLayer('ImageryTransportation');
                overlays['Roads/Transport'] = transport;
                var labels = L.esri.basemapLayer('ImageryLabels');
                overlays['Labels'] = labels;
                var flood = L.esri.dynamicMapLayer({{url: 'https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer', opacity: 0.5}});
                overlays['FEMA Flood Hazards'] = flood;
                var wetlands = L.esri.dynamicMapLayer({{url: 'https://fwspub.wim.usgs.gov/arcgis/rest/services/Wetlands/MapServer', opacity: 0.6}});
                overlays['Wetlands (USFWS)'] = wetlands;
                var windSpeed = L.esri.tiledMapLayer({{url: 'https://gis.asce.org/arcgis/rest/services/ASCE722/w2022_Tile_RC_II/MapServer', opacity: 0.6}});
                overlays['ASCE 7 Wind Speed'] = windSpeed;
                
                var flParcels = L.esri.featureLayer({{
                    url: 'https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0',
                    style: {{color: '#ff7800', weight: 2, opacity: 0.8, fillOpacity: 0}},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var p = feature.properties;
                            var content = '<table><tr><td><b>Parcel ID:</b></td><td>' + (p.PARCEL_ID || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>Owner:</b></td><td>' + (p.OWN_NAME || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>Mailing:</b></td><td>' + (p.OWN_ADDR1 || '') + '<br>' + (p.OWN_CITY || '') + ', ' + (p.OWN_STATE || '') + ' ' + (p.OWN_ZIPCD || '') + '</td></tr>' +
                                          '<tr><td><b>Site Addr:</b></td><td>' + (p.PHY_ADDR1 || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>DOR Use:</b></td><td>' + (p.DOR_UC || 'N/A') + '</td></tr></table>';
                            layer.bindPopup(content);
                            layer.bindTooltip(p.PARCEL_ID || 'Parcel', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['Florida Parcels (owner/details)'] = flParcels;
                
                var cellsLayer = L.markerClusterGroup();
                overlays['Cell Towers'] = cellsLayer;
                var airportsLayer = L.layerGroup();
                overlays['Airports'] = airportsLayer;
                
                L.control.layers(baseLayers, overlays, {{collapsed: false}}).addTo(map);
                satellite.addTo(map);
                
                L.circle([{lat}, {lon}], {{radius: {radius_m}, color: 'yellow', weight: 3, fill: false}}).addTo(map);
                
                {cells_js}
                {airports_js}
                
                map.fitBounds(L.circle([{lat}, {lon}], {{radius: {radius_m}}}).getBounds().pad(0.5));
            </script>
        </body>
        </html>
        """
        
        st.components.v1.html(html_string, height=900, scrolling=True)
    st.success("Map loaded! Toggle layers top-right 👇")
